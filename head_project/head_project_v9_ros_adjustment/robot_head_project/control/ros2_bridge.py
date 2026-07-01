from control.control_mode import ControlMode


class Ros2CommandBridge:
    """
    Optional ROS2 command bridge using only standard ROS2 message packages.

    Topics:
      /robot_head/control_mode  std_msgs/String
      /robot_head/face          std_msgs/String
      /robot_head/pan           std_msgs/Float64
      /robot_head/tilt          std_msgs/Float64
      /robot_head/pose          std_msgs/Float64MultiArray [pan, tilt]
      /robot_head/center        std_msgs/Empty
      /robot_head/stop          std_msgs/Empty
      /robot_head/arm_wave      std_msgs/Empty

    Services:
      /robot_head/center_service   std_srvs/Trigger
      /robot_head/stop_service     std_srvs/Trigger
      /robot_head/arm_wave_service std_srvs/Trigger
    """

    def __init__(self, robot_head, mode_manager, node_name="robot_head_bridge"):
        self.robot_head = robot_head
        self.mode_manager = mode_manager
        self.node = None
        self.rclpy = None
        self.available = False
        self._owns_rclpy_context = False

        try:
            import rclpy
            from rclpy.node import Node
            from std_msgs.msg import Empty, Float64, Float64MultiArray, String
            from std_srvs.srv import Trigger
        except Exception as exc:
            print("ROS2 bridge disabled; ROS2 Python packages unavailable:", exc)
            return

        self.rclpy = rclpy
        if not rclpy.ok():
            rclpy.init(args=None)
            self._owns_rclpy_context = True

        bridge = self

        class RobotHeadBridgeNode(Node):
            def __init__(self):
                super().__init__(node_name)

                self.create_subscription(
                    String,
                    "/robot_head/control_mode",
                    self.control_mode_callback,
                    10,
                )
                self.create_subscription(
                    String,
                    "/robot_head/face",
                    self.face_callback,
                    10,
                )
                self.create_subscription(
                    Float64,
                    "/robot_head/pan",
                    self.pan_callback,
                    10,
                )
                self.create_subscription(
                    Float64,
                    "/robot_head/tilt",
                    self.tilt_callback,
                    10,
                )
                self.create_subscription(
                    Float64MultiArray,
                    "/robot_head/pose",
                    self.pose_callback,
                    10,
                )
                self.create_subscription(
                    Empty,
                    "/robot_head/center",
                    self.center_callback,
                    10,
                )
                self.create_subscription(
                    Empty,
                    "/robot_head/stop",
                    self.stop_callback,
                    10,
                )
                self.create_subscription(
                    Empty,
                    "/robot_head/arm_wave",
                    self.arm_wave_callback,
                    10,
                )

                self.create_service(
                    Trigger,
                    "/robot_head/center_service",
                    self.center_service_callback,
                )
                self.create_service(
                    Trigger,
                    "/robot_head/stop_service",
                    self.stop_service_callback,
                )
                self.create_service(
                    Trigger,
                    "/robot_head/arm_wave_service",
                    self.arm_wave_service_callback,
                )

            def control_mode_callback(self, msg):
                try:
                    bridge.mode_manager.set_mode(msg.data)
                except ValueError as exc:
                    self.get_logger().warning(str(exc))

            def face_callback(self, msg):
                bridge.robot_head.show_face(msg.data, source=ControlMode.ROS)

            def pan_callback(self, msg):
                bridge.robot_head.set_pan(msg.data, source=ControlMode.ROS)

            def tilt_callback(self, msg):
                bridge.robot_head.set_tilt(msg.data, source=ControlMode.ROS)

            def pose_callback(self, msg):
                if len(msg.data) < 2:
                    self.get_logger().warning(
                        "/robot_head/pose requires [pan, tilt]"
                    )
                    return
                bridge.robot_head.set_head_pose(
                    msg.data[0],
                    msg.data[1],
                    source=ControlMode.ROS,
                )

            def center_callback(self, _msg):
                bridge.robot_head.center(source=ControlMode.ROS)

            def stop_callback(self, _msg):
                bridge.robot_head.stop(source=ControlMode.ROS)

            def arm_wave_callback(self, _msg):
                bridge.robot_head.wave_arm(source=ControlMode.ROS)

            @staticmethod
            def _fill_trigger_response(response, success, message):
                response.success = bool(success)
                response.message = message
                return response

            def center_service_callback(self, _request, response):
                success = bridge.robot_head.center(source=ControlMode.ROS)
                return self._fill_trigger_response(
                    response,
                    success,
                    "CENTER sent" if success else "CENTER blocked or not sent",
                )

            def stop_service_callback(self, _request, response):
                success = bridge.robot_head.stop(source=ControlMode.ROS)
                return self._fill_trigger_response(
                    response,
                    success,
                    "STOP sent" if success else "STOP blocked or not sent",
                )

            def arm_wave_service_callback(self, _request, response):
                success = bridge.robot_head.wave_arm(source=ControlMode.ROS)
                return self._fill_trigger_response(
                    response,
                    success,
                    "ARM_WAVE sent" if success else "ARM_WAVE blocked or not sent",
                )

        try:
            self.node = RobotHeadBridgeNode()
            self.available = True
            print("ROS2 command bridge started:", node_name)
        except Exception as exc:
            print("Could not start ROS2 command bridge:", exc)
            self.close()

    def spin_once(self):
        if self.available and self.node is not None:
            self.rclpy.spin_once(self.node, timeout_sec=0.0)

    def close(self):
        if self.node is not None:
            try:
                self.node.destroy_node()
            except Exception:
                pass
            self.node = None

        if (
            self.rclpy is not None
            and self._owns_rclpy_context
            and self.rclpy.ok()
        ):
            try:
                self.rclpy.shutdown()
            except Exception:
                pass

        self.available = False
