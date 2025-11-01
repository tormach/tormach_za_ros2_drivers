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

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.descriptions import ParameterValue

from ament_index_python.packages import get_package_share_directory

from hal_hw_interface.launch import HalConfig, HalRTNode, HalUserNode, HalFiles


def generate_launch_description():
    # Configure some helper variables and paths
    hw_pkg_name = "za6_hardware"
    hw_pkg_share = FindPackageShare(hw_pkg_name)

    moveit_pkg_name = "za6_moveit_config"
    moveit_pkg_share = FindPackageShare(moveit_pkg_name)

    prefix = LaunchConfiguration("prefix")

    # Load URDF content via robot_description.launch.py
    # FIXME This is the right way to do this, but it causes some kind of
    #     circular dependency
    # description_package_share = FindPackageShare(
    #     LaunchConfiguration("description_package")
    # )
    description_package_share = get_package_share_directory("za6_description")
    # /FIXME

    description_launch_py = PythonLaunchDescriptionSource(
        PathJoinSubstitution(
            [
                description_package_share,
                "launch",
                "robot_description.launch.py",
            ]
        )
    )
    robot_description_content = LaunchConfiguration("robot_description_content")

    # launch.substitutions.EqualsSubstitution() coming someday
    # sim = EqualsSubstitution(LaunchConfiguration("sim_mode"), "true")
    sim = PythonExpression(
        ["'", LaunchConfiguration("sim_mode"), "' == 'true'"]
    )

    # Set ros2_control hardware plugin to HAL or fake hardware, depending on
    # `use_fake_hardware` launch arg value
    ros2_control_plugin = PythonExpression(
        [
            "'mock_components/GenericSystem' if '",
            LaunchConfiguration("use_fake_hardware"),
            "' == 'true' else ",
            "'hal_system_interface/HalSystemInterface'",
        ]
    )

    launch_entities = [
        DeclareLaunchArgument(
            "description_package",
            default_value="za6_description",
            description="Description package with robot URDF/XACRO files",
        ),
        DeclareLaunchArgument(
            "description_file",
            default_value="za6.xacro",
            description="URDF/XACRO description file with the robot.",
        ),
        DeclareLaunchArgument(
            "prefix",
            default_value="",
            description=(
                "Prefix of joint names for multi-robot setup; "
                "if changed, controller configuration joint names "
                "must also be updated"
            ),
        ),
        DeclareLaunchArgument(
            "use_fake_hardware",
            default_value="false",
            description="Use ros2_control mock_components/GenericSystem plugin",
        ),
        IncludeLaunchDescription(
            description_launch_py,
            launch_arguments=dict(
                description_package=LaunchConfiguration("description_package"),
                description_file=LaunchConfiguration("description_file"),
                prefix=prefix,
                ros2_control_plugin=ros2_control_plugin,
            ).items(),
        ),
        DeclareLaunchArgument(
            "sim_mode",
            default_value="false",
            description="Run robot with sim HAL hardware",
        ),
        DeclareLaunchArgument(
            "hal_debug_output",
            default_value="true",
            description="Output HAL debug messages to screen (console)",
        ),
        DeclareLaunchArgument(
            "hal_debug_level",
            default_value="1",
            description="Set HAL debug level, 0-5",
        ),
        DeclareLaunchArgument(
            "hal_file_dir",
            default_value=PathJoinSubstitution([hw_pkg_share, "halfiles"]),
            description="Directory containing HAL configuration files.",
        ),
        DeclareLaunchArgument(
            "hal_file",
            default_value="za6.hal.py",
            description="HAL file to load from hal_file_dir.",
        ),
        DeclareLaunchArgument(
            "hal_wait_timeout",
            default_value="30",
            description="Timeout for loading HAL components; default 30s",
        ),
        DeclareLaunchArgument(
            # Used by hw_device_mgr
            "hal_device_config_path",
            default_value=PathJoinSubstitution(
                [
                    hw_pkg_share,
                    "config",
                    "hal_device_config.yaml",
                ]
            ),
            description="Path to HAL device config",
        ),
        DeclareLaunchArgument(
            # Used in HAL config za6.hal.py
            "hardware_settings_yaml",
            default_value=PathJoinSubstitution(
                [
                    hw_pkg_share,
                    "config",
                    "hardware_settings.yaml",
                ]
            ),
            description="YAML param file with per-joint hardware_settings",
        ),
        DeclareLaunchArgument(
            "sim_device_data_path",
            default_value=PathJoinSubstitution(
                [
                    hw_pkg_share,
                    "config",
                    "hal_sim_devices.yaml",
                ]
            ),
            description="Path to sim device configuration YAML file",
        ),
        DeclareLaunchArgument(
            "hal_hw_interface_yaml",
            description="YAML param file with hal_mgr and hardware_interface.",
            default_value=PathJoinSubstitution(
                [
                    hw_pkg_share,
                    "config",
                    "hal_hw_interface.yaml",
                ]
            ),
        ),
        DeclareLaunchArgument(
            "ros2_controllers_yaml",
            description="ROS2 controller manager configuration YAML.",
            default_value=PathJoinSubstitution(
                [
                    moveit_pkg_share,
                    "config",
                    "ros2_controllers.yaml",
                ]
            ),
        ),
        DeclareLaunchArgument(
            "joint_limits_yaml",
            description="Robot joint limits YAML file.",
            default_value=PathJoinSubstitution(
                [
                    moveit_pkg_share,
                    "config",
                    "joint_limits.yaml",
                ]
            ),
        ),
        DeclareLaunchArgument(
            "joint_trajectory_topic",
            description="Joint trajectory controller topic name.",
            default_value="/joint_trajectory_controller/joint_trajectory",
        ),
        DeclareLaunchArgument(
            "drive_state_timeout",
            description="Timeout for drive enable/disable services.",
            default_value="10",
        ),
        DeclareLaunchArgument(
            "drive_state_update_rate",
            description="Update rate for drive state service node (Hz).",
            default_value="10",
        ),
        # HAL configuration & controller manager
        HalConfig(
            # hal_mgr args
            parameters=[
                dict(  # Individual keys
                    hal_debug_output=LaunchConfiguration("hal_debug_output"),
                    hal_debug_level=LaunchConfiguration("hal_debug_level"),
                ),
            ],
            output="both",
            emulate_tty=True,
            log_cmd=True,
            # HAL config
            actions=[
                HalRTNode(
                    package="hal_hw_interface",
                    component="hal_control_node",
                    parameters=[  # ROS parameters from various sources
                        # Individual keys
                        dict(
                            # Expanded robot description URDF
                            robot_description=ParameterValue(
                                robot_description_content, value_type=str
                            ),
                        ),
                        # Controller manager & hardware interface config params
                        LaunchConfiguration("hal_hw_interface_yaml"),
                        # Controller manager controller config params
                        LaunchConfiguration("ros2_controllers_yaml"),
                    ],
                    wait_timeout=LaunchConfiguration("hal_wait_timeout"),
                    log_cmd=True,
                    output="both",
                    emulate_tty=True,
                    # arguments=['--ros-args', '--log-level', 'debug'],
                    # prefix=['xterm -e gdb -ex run --args'],
                ),
                HalUserNode(
                    package=hw_pkg_name,
                    executable="hw_device_mgr",
                    parameters=[
                        dict(  # One-off params
                            # File with HAL device configuration
                            device_config_path=LaunchConfiguration(
                                "hal_device_config_path"
                            ),
                            # File with sim device configuration
                            sim_device_data_path=PythonExpression(
                                [
                                    "'",
                                    LaunchConfiguration("sim_device_data_path"),
                                    "' if ",
                                    sim,
                                    " else ''",
                                ]
                            ),
                        ),
                        PathJoinSubstitution(
                            [
                                hw_pkg_share,
                                "config",
                                "hal_hw_device_mgr.yaml",
                            ]
                        ),
                    ],
                    log_cmd=True,
                    output="both",
                    emulate_tty=True,
                    arguments=[
                        # Add `--sim` if in sim mode, otherwise empty string;
                        # ugly, yes, and should be fixed with proper command
                        # line arg parsing in hw_device_mgr
                        PythonExpression(
                            expression=["'--sim' if ", sim, " else ''"]
                        ),
                        # '--ros-args',
                        # '--log-level', 'debug',
                    ],
                ),
                HalUserNode(
                    package="hal_hw_interface",
                    executable="hal_io",
                    log_cmd=True,
                    output="both",
                    emulate_tty=True,
                    parameters=[
                        PathJoinSubstitution(
                            [
                                hw_pkg_share,
                                "config",
                                "hal_io.yaml",
                            ]
                        ),
                    ],
                    arguments=[
                        PathJoinSubstitution(
                            [
                                hw_pkg_share,
                                "config",
                                "hal_io_config.yaml",
                            ]
                        ),
                    ],
                ),
                HalUserNode(
                    package="za6_hardware",
                    executable="drive_state",
                    parameters=[
                        dict(
                            update_rate=LaunchConfiguration(
                                "drive_state_update_rate"
                            ),
                            timeout=LaunchConfiguration("drive_state_timeout"),
                            joint_trajectory_topic=LaunchConfiguration(
                                "joint_trajectory_topic"
                            ),
                            # File with HAL device configuration
                            device_config_path=LaunchConfiguration(
                                "hal_device_config_path"
                            ),
                            # Sim drive configuration
                            sim_device_data_path=PythonExpression(
                                [
                                    "'",
                                    LaunchConfiguration("sim_device_data_path"),
                                    "' if ",
                                    sim,
                                    " else ''",
                                ]
                            ),
                            # Sim
                            sim_mode=sim,
                        ),
                    ],
                    log_cmd=True,
                    output="both",
                    emulate_tty=True,
                ),
                HalFiles(
                    hal_file_dir=LaunchConfiguration("hal_file_dir"),
                    hal_files=[LaunchConfiguration("hal_file")],
                    parameters=[
                        dict(
                            # File with HAL device configuration
                            device_config_path=LaunchConfiguration(
                                "hal_device_config_path"
                            ),
                            # File with sim device configuration
                            sim_device_data_path=LaunchConfiguration(
                                "sim_device_data_path"
                            ),
                            # Sim (true) or hardware (false)
                            sim_mode=LaunchConfiguration("sim_mode"),
                        ),
                        PathJoinSubstitution(
                            [
                                hw_pkg_share,
                                "config",
                                "hal_config.yaml",
                            ]
                        ),
                        LaunchConfiguration("joint_limits_yaml"),
                        LaunchConfiguration("hardware_settings_yaml"),
                    ],
                ),
            ],
            condition=UnlessCondition(LaunchConfiguration("use_fake_hardware")),
        ),
        # Safety stop node (mirrors ROS1 drive_safety behavior subset)
        Node(
            package=hw_pkg_name,
            executable="safety_stop.py",
            name="safety_stop",
            output="screen",
            parameters=[
                dict(unsafe_vel_limit=0.10),
            ],
            condition=UnlessCondition(LaunchConfiguration("use_fake_hardware")),
        ),
        # Fake hardware configuration & controller manager
        Node(
            package="controller_manager",
            executable="ros2_control_node",
            parameters=[  # ROS parameters from various sources
                # Individual keys
                dict(
                    # Expanded robot description URDF
                    robot_description=ParameterValue(
                        robot_description_content, value_type=str
                    ),
                ),
                # Controller manager controller config params
                LaunchConfiguration("ros2_controllers_yaml"),
            ],
            output="screen",
            condition=IfCondition(LaunchConfiguration("use_fake_hardware")),
        ),
        # Launch joint_trajectory_controller and joint_state_broadcaster
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution(
                    [
                        moveit_pkg_share,
                        "launch",
                        "spawn_controllers.launch.py",
                    ]
                )
            ),
        ),
    ]

    return LaunchDescription(launch_entities)
