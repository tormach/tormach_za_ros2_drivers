#!/usr/bin/env python
#
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


import rclpy
from machinekit import hal
import time

logger = rclpy.logging.get_logger("ZA_hal_config_robot_io_pins")


def setup_sim_pins():
    logger.info('Creating io-rcomp HAL remote component')
    # mirror hal_io to rcomp
    hal_io = hal.components['hal_io']
    rcomp = hal.RemoteComponent('io-rcomp', timer=100)
    for pin in hal_io.pins():
        name = '.'.join(pin.name.split('.')[1:])
        if not name.startswith('digital_'):
            continue
        dir_map = {hal.HAL_IN: hal.HAL_IO, hal.HAL_OUT: hal.HAL_IN}
        rcomp.newpin(name, pin.type, dir_map.get(pin.dir, hal.HAL_IO))
        if pin.dir == hal.HAL_IN:
            rcomp.pin(name).link(hal.pins[pin.name])
        else:
            hal.pins[pin.name].link(rcomp.pin(name))
    rcomp.ready()
    logger.info('io-rcomp HAL remote component ready')

    hal.loadusr('haltalk')

    hal.Signal("safety_input").set(True)


def link_hal_io_pins_from_map(signal_to_pin_map):
    for hal_sig_name, pins in signal_to_pin_map.items():
        lcec_pin_name = pins[0]
        # by default, io pin name is the same as the signal, unless overridden with a specific name
        hal_io_pin_name = f"hal_io.{pins[1] or hal_sig_name}"
        logger.info(
            f"Linking {hal_sig_name}: {lcec_pin_name} {hal_io_pin_name}"
        )
        hal.Signal(hal_sig_name).link(lcec_pin_name)
        hal.Signal(hal_sig_name).link(hal_io_pin_name)


is620n_signal_to_pin_map = {
    "enabling_input": ("lcec.0.6.din-14", "digital_in_15"),
    "safety_input": ("lcec.0.6.din-15", "digital_in_16"),
}

# Add in standard signals
is620n_signal_to_pin_map.update(
    {f"digital_in_{n + 1}": (f"lcec.0.6.din-{n}", "") for n in range(14)}
)
is620n_signal_to_pin_map.update(
    {f"digital_out_{n + 1}": (f"lcec.0.6.dout-{n}", "") for n in range(14)}
)


def setup_lcec_is620n_pins():
    logger.info('Connecting IS620N lcec pins')
    link_hal_io_pins_from_map(is620n_signal_to_pin_map)

    logger.info('Finished connecting IS602N lcec pins')


sv660n_signal_to_pin_map = {
    # Map DIO signals to drive pins according to ethercat.xml and IO integration
    # board
    #
    # Digital inputs:  SV660 has five DIs; use 2-5 on first three drives
    "digital_in_1": ("lcec.0.0.di2", ""),
    "digital_in_2": ("lcec.0.0.di3", ""),
    "digital_in_3": ("lcec.0.0.di4", ""),
    "digital_in_4": ("lcec.0.0.di5", ""),
    "digital_in_5": ("lcec.0.1.di2", ""),
    "digital_in_6": ("lcec.0.1.di3", ""),
    "digital_in_7": ("lcec.0.1.di4", ""),
    "digital_in_8": ("lcec.0.1.di5", ""),
    "digital_in_9": ("lcec.0.2.di2", ""),
    "digital_in_10": ("lcec.0.2.di3", ""),
    "enabling_input": ("lcec.0.2.di4", "digital_in_11"),
    "safety_input": ("lcec.0.2.di5", "digital_in_12"),
    # Digital Outputs:  SV660 has three DOs; DO3 used for brakes
    "digital_out_1": ("lcec.0.0.do1", ""),
    "digital_out_2": ("lcec.0.0.do2", ""),
    "digital_out_3": ("lcec.0.1.do1", ""),
    "digital_out_4": ("lcec.0.1.do2", ""),
    "digital_out_5": ("lcec.0.2.do1", ""),
    "digital_out_6": ("lcec.0.2.do2", ""),
    "digital_out_7": ("lcec.0.3.do1", ""),
    "digital_out_8": ("lcec.0.3.do2", ""),
    "digital_out_9": ("lcec.0.4.do1", ""),
    "digital_out_10": ("lcec.0.4.do2", ""),
    "digital_out_11": ("lcec.0.5.do1", ""),
    "digital_out_12": ("lcec.0.5.do2", ""),
}


def setup_lcec_sv660n_pins():
    logger.info('Connecting SV660N lcec pins')
    link_hal_io_pins_from_map(sv660n_signal_to_pin_map)
    logger.info('Finished connecting SV660N lcec pins')


def setup_hal_mgr_pins():
    logger.info('Connecting hal_mgr pins')
    hal.Signal('state_cmd').link('hal_io.state_cmd')
    logger.info('Finished connecting hal_mgr pins')


def setup_controller_pins():
    # Controller error code
    hal.Signal('controller_error_code').link(
        hal.Pin('hal_io.controller_error_code')
    )

    # Link probe pin polarity selection to hal_hw_interface
    hal.Signal('probe_signal_active_low').link(
        hal.Pin('hal_io.probe_active_low')
    )
    hal.Signal('probe_actual').link(hal.Pin('hal_io.probe_in'))
    time.sleep(1)
    # FIXME This needs rework
    # saved_probe_passive = rospy.get_param('/user_config/probe/passive')
    # logger.info(
    #     "Restoring saved probe polarity setting: "
    #     f"{'passive' if saved_probe_passive else 'active'}"
    # )
    # hal.Signal('probe_signal_active_low').set(saved_probe_passive)


def setup_safety_input_pins():
    logger.info('Connecting hal pins for safety input')
    hal.Signal("safety_input").link(hal.Pin("hal_io.safety_input"))
    hal.Signal("enabling_input").link(hal.Pin("hal_io.enabling_input"))
    hal.Signal("max_vel_safety_scale").link(
        hal.Pin("hal_io.max_vel_safety_scale")
    )

    # Quick stop
    hal.Signal('quick_stop').link(hal.Pin('hal_io.quick_stop'))
    # External quick stop input (from ROS topic to drive_safety)
    hal.Signal('quick_stop_ext').link(hal.Pin('hal_io.quick_stop_ext'))

    logger.info('Finished connecting hal pins for safety input')


drive_to_setup_map = {
    "SV660N": setup_lcec_sv660n_pins,
    "IS620N": setup_lcec_is620n_pins,
}


def setup_pins(params):
    setup_safety_input_pins()

    if params["sim_mode"]:
        setup_sim_pins()
    else:
        # FIXME This needs hw_device_mgr detection
        # hardware_version = rospy.get_param('/hal_mgr/hardware_version')
        # setup_func = drive_to_setup_map[hardware_version]
        # setup_func()
        pass
    setup_hal_mgr_pins()
    setup_controller_pins()
