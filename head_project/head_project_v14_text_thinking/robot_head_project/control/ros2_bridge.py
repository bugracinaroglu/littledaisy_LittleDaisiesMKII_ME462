from control.control_mode import ControlMode


class Ros2CommandBridge:
    """Optional ROS2 bridge using standard ROS2 message packages.

    String payload examples:
      /robot_head/face:     "THINKING,4000"
      /robot_head/text:     "Hello Daisy"
      /robot_head/text:     "5000|1|Oopsie Daisy"
      /robot_head/gesture:  "DANCE,3,7000"

    Text payload format:
      text
      hold_ms|italic|text

    italic accepts 1/0, true/false, yes/no, or italic/normal.
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
                    String, "/robot_head/control_mode",
                    self.control_mode_callback, 10,
                )
                self.create_subscription(
                    String, "/robot_head/face", self.face_callback, 10,
                )
                self.create_subscription(
                    String, "/robot_head/text", self.text_callback, 10,
                )
                self.create_subscription(
                    String, "/robot_head/gesture", self.gesture_callback, 10,
                )
                self.create_subscription(
                    Float64, "/robot_head/pan", self.pan_callback, 10,
                )
                self.create_subscription(
                    Float64, "/robot_head/tilt", self.tilt_callback, 10,
                )
                self.create_subscription(
                    Float64MultiArray, "/robot_head/pose", self.pose_callback, 10,
                )
                self.create_subscription(
                    Empty, "/robot_head/center", self.center_callback, 10,
                )
                self.create_subscription(
                    Empty, "/robot_head/stop", self.stop_callback, 10,
                )
                self.create_subscription(
                    Empty, "/robot_head/arm_wave", self.arm_wave_callback, 10,
                )
                self.create_subscription(
                    Empty, "/robot_head/cancel_gesture",
                    self.cancel_gesture_callback, 10,
                )
                self.create_subscription(
                    Empty, "/robot_head/oopsie_daisy",
                    self.oopsie_daisy_callback, 10,
                )
                self.create_subscription(
                    Empty, "/robot_head/thinking",
                    self.thinking_callback, 10,
                )

                self.create_service(
                    Trigger, "/robot_head/center_service",
                    self.center_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/stop_service",
                    self.stop_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/arm_wave_service",
                    self.arm_wave_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/nod_service",
                    self.nod_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/sunglasses_nod_service",
                    self.sunglasses_nod_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/sigma_nod_service",
                    self.sigma_nod_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/dance_service",
                    self.dance_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/greet_service",
                    self.greet_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/daisy_dance_service",
                    self.daisy_dance_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/cancel_gesture_service",
                    self.cancel_gesture_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/oopsie_daisy_service",
                    self.oopsie_daisy_service_callback,
                )
                self.create_service(
                    Trigger, "/robot_head/thinking_service",
                    self.thinking_service_callback,
                )

            @staticmethod
            def _split_payload(payload):
                return [part.strip() for part in str(payload).split(",")]

            def _parse_face_payload(self, payload):
                parts = self._split_payload(payload)
                if not parts or not parts[0] or len(parts) > 2:
                    raise ValueError("face payload must be FACE or FACE,hold_ms")
                hold_ms = int(parts[1]) if len(parts) == 2 and parts[1] else 0
                return parts[0], max(0, hold_ms)

            def _parse_gesture_payload(self, payload):
                parts = self._split_payload(payload)
                if not parts or not parts[0] or len(parts) > 3:
                    raise ValueError(
                        "gesture payload must be NAME[,count[,hold_ms]]"
                    )
                count = None
                hold_ms = None
                if len(parts) >= 2 and parts[1]:
                    count = max(1, int(parts[1]))
                if len(parts) >= 3 and parts[2]:
                    hold_ms = max(0, int(parts[2]))
                return parts[0], count, hold_ms

            @staticmethod
            def _parse_bool_token(token):
                token = str(token).strip().lower()
                if token in ("1", "true", "yes", "italic"):
                    return True
                if token in ("0", "false", "no", "normal"):
                    return False
                raise ValueError("italic must be 1/0, true/false, or italic/normal")

            def _parse_text_payload(self, payload):
                payload = str(payload).strip()
                if not payload:
                    raise ValueError("text payload cannot be empty")

                if "|" not in payload:
                    return payload, 4000, False

                parts = payload.split("|", 2)
                if len(parts) != 3:
                    raise ValueError(
                        "text payload must be text or hold_ms|italic|text"
                    )

                hold_ms = max(0, int(parts[0].strip()))
                italic = self._parse_bool_token(parts[1])
                text = parts[2].strip()
                if not text:
                    raise ValueError("text payload cannot be empty")
                return text, hold_ms, italic

            def control_mode_callback(self, msg):
                try:
                    bridge.mode_manager.set_mode(msg.data)
                except ValueError as exc:
                    self.get_logger().warning(str(exc))

            def face_callback(self, msg):
                try:
                    face_name, hold_ms = self._parse_face_payload(msg.data)
                    bridge.robot_head.show_face(
                        face_name,
                        hold_ms=hold_ms,
                        source=ControlMode.ROS,
                    )
                except Exception as exc:
                    self.get_logger().warning(str(exc))

            def text_callback(self, msg):
                try:
                    text, hold_ms, italic = self._parse_text_payload(msg.data)
                    bridge.robot_head.show_text(
                        text,
                        hold_ms=hold_ms,
                        italic=italic,
                        source=ControlMode.ROS,
                    )
                except Exception as exc:
                    self.get_logger().warning(str(exc))

            def gesture_callback(self, msg):
                try:
                    name, count, hold_ms = self._parse_gesture_payload(msg.data)
                    bridge.robot_head.play_gesture(
                        name,
                        count=count,
                        hold_ms=hold_ms,
                        source=ControlMode.ROS,
                    )
                except Exception as exc:
                    self.get_logger().warning(str(exc))

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
                    msg.data[0], msg.data[1], source=ControlMode.ROS,
                )

            def center_callback(self, _msg):
                bridge.robot_head.center(source=ControlMode.ROS)

            def stop_callback(self, _msg):
                bridge.robot_head.stop(source=ControlMode.ROS)

            def arm_wave_callback(self, _msg):
                bridge.robot_head.wave_arm(source=ControlMode.ROS)

            def cancel_gesture_callback(self, _msg):
                bridge.robot_head.cancel_gesture(source=ControlMode.ROS)

            def oopsie_daisy_callback(self, _msg):
                bridge.robot_head.show_oopsie_daisy(source=ControlMode.ROS)

            def thinking_callback(self, _msg):
                bridge.robot_head.show_thinking(source=ControlMode.ROS)

            @staticmethod
            def _fill_trigger_response(response, success, message):
                response.success = bool(success)
                response.message = message
                return response

            def _trigger(self, response, success, success_message, failure_message):
                return self._fill_trigger_response(
                    response,
                    success,
                    success_message if success else failure_message,
                )

            def center_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.center(source=ControlMode.ROS),
                    "CENTER sent", "CENTER blocked or not sent",
                )

            def stop_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.stop(source=ControlMode.ROS),
                    "STOP sent", "STOP blocked or not sent",
                )

            def arm_wave_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.wave_arm(source=ControlMode.ROS),
                    "ARM_WAVE sent", "ARM_WAVE blocked or not sent",
                )

            def nod_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.nod_head(source=ControlMode.ROS),
                    "NOD sent", "NOD blocked or not sent",
                )

            def sunglasses_nod_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.sunglasses_nod(source=ControlMode.ROS),
                    "SUNGLASSES_NOD sent",
                    "SUNGLASSES_NOD blocked or not sent",
                )

            def sigma_nod_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.sigma_nod(source=ControlMode.ROS),
                    "SIGMA_NOD sent", "SIGMA_NOD blocked or not sent",
                )

            def dance_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.dance(source=ControlMode.ROS),
                    "DANCE sent", "DANCE blocked or not sent",
                )

            def greet_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.greet(source=ControlMode.ROS),
                    "GREET sent", "GREET blocked or not sent",
                )

            def daisy_dance_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.daisy_dance(source=ControlMode.ROS),
                    "DAISY_DANCE sent", "DAISY_DANCE blocked or not sent",
                )

            def cancel_gesture_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.cancel_gesture(source=ControlMode.ROS),
                    "Gesture cancel sent",
                    "Gesture cancel blocked or not sent",
                )

            def oopsie_daisy_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.show_oopsie_daisy(source=ControlMode.ROS),
                    "Oopsie Daisy displayed",
                    "Oopsie Daisy blocked or not sent",
                )

            def thinking_service_callback(self, _request, response):
                return self._trigger(
                    response,
                    bridge.robot_head.show_thinking(source=ControlMode.ROS),
                    "THINKING face displayed",
                    "THINKING face blocked or not sent",
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
