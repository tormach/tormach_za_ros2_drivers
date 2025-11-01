#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32, UInt32
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy


class SafetyStopNode(Node):
    def __init__(self):
        super().__init__('safety_stop')

        # Parameters
        self.declare_parameter('unsafe_vel_limit', 0.10)  # fraction of max

        # State
        self.safety_input = True
        self.enabling_input = True

        # Publishers (ROS2 analogs of HAL pins)
        # Publish to hal_io/* so HAL consumes them
        self.pub_max_vel_scale = self.create_publisher(
            Float32, '/hal_io/max_vel_safety_scale', 10
        )
        # Use quick_stop_ext which is wired to drive_safety.quick-stop-ext
        self.pub_quick_stop = self.create_publisher(
            Bool, '/hal_io/quick_stop_ext', 10
        )
        self.pub_state_cmd = self.create_publisher(
            UInt32, '/hal_io/state_cmd', 10
        )  # one-shot quick stop command value 4

        # Inputs from digital IO (match HAL IO QoS: Best Effort, keep last 1)
        din_qos = QoSProfile(depth=1)
        din_qos.reliability = QoSReliabilityPolicy.BEST_EFFORT
        din_qos.history = QoSHistoryPolicy.KEEP_LAST
        self.sub_enable = self.create_subscription(
            Bool, '/din15', self._enabling_cb, din_qos
        )
        self.sub_safety = self.create_subscription(
            Bool, '/din16', self._safety_cb, din_qos
        )

        # Initial publish (safe)
        self._publish_state(apply_quick_stop=False)

    def _enabling_cb(self, msg: Bool):
        self.enabling_input = bool(msg.data)
        self._evaluate()

    def _safety_cb(self, msg: Bool):
        self.safety_input = bool(msg.data)
        self._evaluate()

    def _evaluate(self):
        # Mirror ROS1 drive_safety behavior subset:
        # Hard stop policy: If safety_input is low -> QUICK STOP (regardless of enabling_input)
        unsafe_vel = float(self.get_parameter('unsafe_vel_limit').value)

        apply_quick_stop = not self.safety_input
        self._publish_state(
            apply_quick_stop=apply_quick_stop, unsafe_vel=unsafe_vel
        )

    def _publish_state(self, apply_quick_stop: bool, unsafe_vel: float = 0.10):
        # Velocity scaling
        scale_msg = Float32()
        scale_msg.data = 1.0 if self.safety_input else float(unsafe_vel)
        self.pub_max_vel_scale.publish(scale_msg)

        # Quick stop flag
        qs_msg = Bool()
        qs_msg.data = bool(apply_quick_stop)
        self.pub_quick_stop.publish(qs_msg)

        # One-shot quick stop command when going into quick stop
        if apply_quick_stop:
            cmd = UInt32()
            cmd.data = 4  # matches ROS1 quick_stop_command_value default
            self.pub_state_cmd.publish(cmd)


def main():
    rclpy.init()
    node = SafetyStopNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
