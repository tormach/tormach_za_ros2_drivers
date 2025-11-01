# Copyright (c) 2023 Tormach, Inc.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#
#    * Neither the name of the {copyright_holder} nor the names of its
#      contributors may be used to endorse or promote products derived from
#      this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import subprocess
import tempfile
import os
import re
from functools import cached_property
from hal_hw_interface.loadrt_local import loadrt_local, rtapi, hal
from hw_device_mgr.lcec.config import LCECConfig
from hw_device_mgr.config_io import ConfigIO
from .hw_device_mgr import ZADrives, ZASimDrives

from .base import HALPlumberBase
from .joint import HALJointPlumberEC, HALJointPlumberSim


###########################################
# HALPlumber and subclasses
#
# This does the top-level configuration, including running the above
# joint-level configuration; subclass for specific drives


class HALPlumber(HALPlumberBase):
    # Subclasses must define these
    mode_name = "Invalid"
    joint_plumber_class = None
    drive_cls = None

    bus = 0
    appTimePeriod = 1000000
    refClockSyncCycles = 1

    # FIXME this should be pruned down
    num_dios = 16

    def __init__(self, params):
        assert 'sim_mode' in params
        mode = "sim" if params["sim_mode"] else "EtherCAT"
        name = f"ZA HAL {mode} config"
        super().__init__(name, params)
        self.params = params
        self.logger.info("Initializing top-level config")
        self.logger.info(f"Hardware:  {mode}")

        # FIXME
        from pprint import pformat

        self.logger.info(f"HAL file params:  {pformat(params)}")

        self.thread_name = params["hal_thread"]["name"]

    @cached_property
    def num_joints(self):
        return len(self.params["hardware_settings"])

    def setup_hal(self):
        # This represents the high-level work of setting up HAL
        # - Initialize plumbing
        self.init_plumbing()

        # - Set up safety input max_vel_safety scaling
        self.setup_drive_safety()
        # - Connect the device manager
        self.setup_device_mgr()
        # - Connect HAL <-> ROS IO
        self.setup_hal_io()
        # - Connect HAL <-> drive state
        self.setup_drive_state()
        # - Configure the hal_hw_interface comp
        self.configure_hal_hw_interface()
        # - Top-level drive set-up (in subclasses)
        self.setup_drive()
        # - Per-joint set-up
        self.joints = []
        for jname in self.params["hardware_settings"]:
            joint = self.joint_plumber_class(jname, self.params)
            self.joints.append(joint)
            joint.setup_hal()

        # - Load the latency comp
        self.setup_latency()

        # - Set up thread, add functions, start thread
        self.instantiate_threads()

    def init_plumbing(self):
        # Load locally-build icomps; instances to be created later
        loadrt_local('limit3v3')
        hal.newsig('load', hal.HAL_BIT)
        # loadrt_local('ppi')
        loadrt_local('pll')
        # loadrt_local('est')
        loadrt_local('latency')
        loadrt_local('qc')
        hal.newsig("curr_period", hal.HAL_S32)
        hal.newsig("curr_periodf", hal.HAL_FLOAT)
        hal.newsig("control_mode", hal.HAL_S32)

        # Device mgr
        hal.newsig('mgr_state_cmd', hal.HAL_U32)
        hal.newsig('mgr_state_set', hal.HAL_BIT)
        hal.newsig('mgr_state_fb', hal.HAL_U32)
        hal.newsig('mgr_goal_reached', hal.HAL_BIT)

        # Create DIO signals
        for ix in range(1, self.num_dios + 1):
            hal.newsig(f"din{ix:02}", hal.HAL_BIT)
            hal.newsig(f"dout{ix:02}", hal.HAL_BIT)

        # Load device_config.yaml
        device_config_path = self.params["device_config_path"]
        self.logger.info(f"Loading device config from {device_config_path}")
        self.device_config = ConfigIO.load_yaml_path(device_config_path)
        bus_conf = dict(
            appTimePeriod=self.appTimePeriod,
            refClockSyncCycles=self.refClockSyncCycles,
        )
        self.device_bus_config = {0: bus_conf}

        # Set device configuration
        self.drive_cls.set_device_config(self.device_config)

        # Read SDO, DC info
        self.drive_cls.add_device_sdos_from_esi()
        self.drive_cls.add_device_dcs_from_esi()

        # Scan bus devices
        self.params["device_configs"] = self.drive_cls.config_class.scan_bus(
            self.bus
        )
        assert self.params["device_configs"], "No devices found!"
        self.logger.info("Bus scan results:")
        for conf in self.params["device_configs"]:
            self.logger.info(f"  {conf.address}:  {conf.model_id}")

    def setup_drive_safety(self):
        # Desired behavior:
        # - Safety input high:  Drives run at full speed at next motion
        # - Safety input low, falling edge:  Drives quick stop
        # - Safety input low:
        #   - Enabling input low:  Drives cannot start
        #   - Enabling input high:  Drives can start & run at 10% speed

        loadrt_local('drive_safety')
        rtapi.newinst(
            'drive_safety', 'drive_safety', drivecount=self.num_joints
        )
        self.func_config("drive_safety", self.Prio.SAFETY_CHAIN + 10)

        #  Safety input signal:  Safe high
        safety_input_sig = hal.newsig("safety_input", hal.HAL_BIT)
        safety_input_sig.link("drive_safety.safety-input")
        safety_input_sig.set(1)  # For sim

        #  Enabling (deadman) device input:  Enable high
        enabling_input_sig = hal.newsig("enabling_input", hal.HAL_BIT)
        enabling_input_sig.link("drive_safety.enabling-input")
        enabling_input_sig.set(1)  # For sim

        #  Velocity safety scale:  reduce velocity to 10% when safety input low
        # FIXME
        max_vel_safety_scale = 0.1
        # max_vel_safety_scale = rospy.get_param(
        #     '/hardware_interface/max_vel_safety_scale', 0.1
        # )
        hal.Pin("drive_safety.unsafe-vel-limit").set(max_vel_safety_scale)
        max_vel_scale_sig = hal.newsig("max_vel_safety_scale", hal.HAL_FLOAT)
        max_vel_scale_sig.link(hal.Pin("drive_safety.vel-limit"))

    def setup_device_mgr(self):
        # Link hw_device_mgr signals
        hal.Signal('mgr_state_cmd').link('hw_device_mgr.state_cmd')
        hal.Signal('mgr_state_set').link('hw_device_mgr.state_set')
        hal.Signal('mgr_state_fb').link('hw_device_mgr.state')  # Writer
        hal.Signal('mgr_goal_reached').link('hw_device_mgr.goal_reached')

    def setup_hal_io(self):
        # Link hal_io signals
        hal.Signal('control_mode').link('hal_io.control_mode')  # Writer

        for ix in range(1, self.num_dios + 1):
            hal.Signal(f"din{ix:02}").link(f"hal_io.din{ix:02}")
            hal.Signal(f"dout{ix:02}").link(f"hal_io.dout{ix:02}")  # Writer

        # Safety-related IO wiring (runs after hal_io is up)
        # - External quick stop from ROS topic → drive_safety
        qse_sig = hal.newsig('quick_stop_ext', hal.HAL_BIT)
        qse_sig.link('drive_safety.quick-stop-ext')
        qse_sig.link('hal_io.quick_stop_ext')

        # Note: do not link 'hal_io.state_cmd' here to avoid multiple writers on
        # 'mgr_state_cmd'. Quick stop is handled via 'quick_stop_ext' and drive_safety.

    def setup_drive_state(self):
        hal.Signal('mgr_state_cmd').link('drive_state.state_cmd')  # Writer
        hal.Signal('mgr_state_set').link('drive_state.state_set')  # Writer
        hal.Signal('mgr_state_fb').link('drive_state.state_fb')
        hal.Signal('mgr_goal_reached').link('drive_state.goal_reached')
        hal.Signal('load').link('drive_state.load')

    def configure_hal_hw_interface(self):
        # Run the hal_hw_interface function right in the middle
        self.func_config("hal_control_node.funct", self.Prio.ROS_CONTROL)

    def setup_drive(self):
        # Override in classes that need a drive setup routine
        raise RuntimeError("Subclasses must implement setup_drive() method")

    def setup_latency(self):
        rtapi.newinst("latency", "latency")
        self.func_config("latency.funct", self.Prio.CMD_CHAIN + 20)
        hal.Signal('curr_period').link("latency.curr-period")
        hal.Signal('curr_periodf').link("latency.curr-periodf")

    def get_isolcpus(self):
        with open("/proc/cmdline") as f:
            cmdline = f.read().strip()
        for arg in cmdline.split(" "):
            if arg.startswith("isolcpus="):
                return arg[9:]
        else:
            return None

    def run_cmd(self, *args):
        self.logger.debug(f"Running shell command:  '{' '.join(args)}'")
        res = subprocess.check_output(args).decode().strip()
        self.logger.debug(f"  Output:  '{res}'")
        return res

    def create_cgroup(self, cgname):
        self.isolcpus = None
        self.logger.info(f"Checking cpuset cgroup '{cgname}'")
        try:
            res = self.run_cmd("cgget", "-nvr", "cpuset.cpus", cgname)
        except subprocess.CalledProcessError:
            # In Jammy, this can mean the cgroup isn't yet configured
            res = None
        if res:
            self.logger.info(f"Cpuset cgroup '{cgname}' exists:  {res}")
            self.isolcpus = res
            return True

        isolcpus = self.isolcpus = self.get_isolcpus()
        if isolcpus is None:
            self.logger.warn(
                "Not configuring cgroup '{cgname}': no `isolcpus=` kernel arg"
            )
            return False
        self.logger.info(f"Creating cpuset cgroup '{cgname}'")
        self.run_cmd("sudo", "cgcreate", "-g", f"cpuset:{cgname}")
        if not self.run_cmd("lscgroup", "-g", f"cpuset:{cgname}"):
            self.logger.info("  Failed")
            return False
        self.logger.info("    Setting cpuset.mems=0")
        self.run_cmd("sudo", "cgset", "-r", "cpuset.mems=0", cgname)
        if not self.run_cmd("cgget", "-nvr", "cpuset.mems", cgname) == "0":
            self.logger.info("  Failed")
            return False
        self.logger.info(f"    Setting cpuset.cpus={isolcpus}")
        self.run_cmd("sudo", "cgset", "-r", f"cpuset.cpus={isolcpus}", cgname)
        res = self.run_cmd("cgget", "-nvr", "cpuset.cpus", cgname)
        if res:
            self.logger.info(f"   New cpuset cgroup {cgname} created:  {res}")
            return True
        else:
            self.logger.warn(f"Unable to create cpuset cgroup '{cgname}'")
            return False

    isolcpus_re = re.compile(r"([0-9]+).*")

    def instantiate_threads(self):
        # Init HAL thread, maybe setting cgroup
        kwargs = dict()
        cgname = self.hal_thread.get("rt_cgname", None)
        kwargs_str = ""
        if cgname is not None and self.create_cgroup(cgname):
            m = self.isolcpus_re.match(self.isolcpus)
            isolcpu = int(m.group(1))  # Pick first CPU in group (it's easy)
            kwargs.update(cpu=isolcpu)
            kwargs_str += f", cpu={isolcpu}"
        thread_period = self.hal_thread["period"]
        thread_name = self.hal_thread["name"]
        self.logger.info(
            f"Thread:  {thread_name}, {thread_period}, fp=True{kwargs_str}"
        )
        rtapi.newthread(thread_name, thread_period, fp=True, **kwargs)
        # Add functions to thread in correct order
        self.add_funcs()
        hal.Signal('curr_period').link("robot_hw_thread.curr-period")


class HALPlumberEC(HALPlumber):
    name = "EtherCAT top HAL config"
    mode_name = "EtherCAT"
    joint_plumber_class = HALJointPlumberEC
    drive_cls = ZADrives

    def init_plumbing(self):
        super().init_plumbing()

        # IO module signals
        self.have_itegva = False
        itegva_dev_cls = self.drive_cls.get_model_by_name("ZA_E7.820.003")
        itegva_model_id = itegva_dev_cls.device_model_id()
        d_confs = self.params["device_configs"]
        if len(d_confs) > 6 and d_confs[6].model_id == itegva_model_id:
            self.have_itegva = True
            self.logger.info("  iTegva DIO module attached")
            for name in ("online", "oper"):
                hal.newsig(f"io_module_{name}", hal.HAL_BIT)
        self.params["have_itegva"] = self.have_itegva  # For joint.py

    def gen_lcec_conf(self):
        # Generate ethercat.xml contents
        conf = LCECConfig.gen_ethercat_xml(self.device_bus_config)

        # Write ethercat.conf.xml file and return path
        suffix = ".ethercat.conf.xml"
        ecat_conf_file = tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False
        )
        self.logger.info(f"  ethercat.conf.xml in {ecat_conf_file.name}")
        ecat_conf_file.write(conf)
        ecat_conf_file.close()
        return ecat_conf_file.name

    def setup_device_mgr(self):
        super().setup_device_mgr()
        if self.have_itegva:
            for name in ("online", "oper"):
                sig = hal.Signal(f"io_module_{name}")
                sig.link(f"hw_device_mgr.0.6.0.{name}")

    def setup_drive(self):
        # Configure and load lcec component
        lcec_conf_file = self.gen_lcec_conf()
        assert os.path.exists(lcec_conf_file)
        self.logger.info(f"Loading lcec_conf with config {lcec_conf_file}")
        hal.loadusr(f"lcec_conf {lcec_conf_file}", wait=True, wait_timeout=10.0)
        self.logger.info("Loading lcec component")
        rtapi.loadrt("lcec")

        # Connect IO module here
        if self.have_itegva:
            for name in ("online", "oper"):
                sig = hal.Signal(f"io_module_{name}")
                sig.link(f"lcec.0.6.slave-{name}")
            for idx in range(16):
                hal.Signal(f"din{idx + 1:02d}").link(f"lcec.0.6.din-{idx}")
                hal.Signal(f"dout{idx + 1:02d}").link(f"lcec.0.6.dout-{idx}")

        # Read fb at beginning of cycle, write cmd at end
        self.func_config("lcec.0.read", self.Prio.DRIVE_READ_FB)
        self.func_config("lcec.0.write", self.Prio.DRIVE_WRITE_CMD + 10)


class HALPlumberSim(HALPlumber):
    name = "Sim top HAL config"
    mode_name = "sim"
    joint_plumber_class = HALJointPlumberSim
    drive_cls = ZASimDrives

    def init_plumbing(self):
        # Read sim device configuration
        sim_device_data_path = self.params["sim_device_data_path"]
        self.logger.info(f"Loading device config from {sim_device_data_path}")
        self.sim_device_data = ConfigIO.load_yaml_path(sim_device_data_path)
        self.drive_cls.init_sim(sim_device_data=self.sim_device_data)

        super().init_plumbing()

    def setup_drive(self):
        # See HALJointPlumberSim.connect_drive() for info

        # sim_start_pos signal:  when True, load start position
        # - oneshot for triggering load once at startup
        rtapi.newinst('oneshot', 'sim_start_pos')
        self.func_config('sim_start_pos.funct', self.Prio.DRIVE_READ_FB)
        # - go high for a short time, only once
        hal.Pin('sim_start_pos.width').set(0.1)
        hal.Pin('sim_start_pos.retriggerable').set(False)
        hal.Pin('sim_start_pos.in').set(True)
        # - signal will connect to sim_drive.load and to sim_pos_sel input
        ssp_sig = hal.newsig('sim_start_pos', hal.HAL_BIT)
        ssp_sig.link('sim_start_pos.out')

        # sim_pos_sel signal:  switch btw. start and ROS cmd positions
        rtapi.newinst("conv_bit_s32", "sim_pos_sel")
        self.func_config('sim_pos_sel.funct', self.Prio.DRIVE_READ_FB + 1)
        ssp_sig.link('sim_pos_sel.in')
        # - signal will connect to sim_pos_channel inputs
        sps_sig = hal.newsig('sim_pos_sel', hal.HAL_S32)
        sps_sig.link('sim_pos_sel.out')
