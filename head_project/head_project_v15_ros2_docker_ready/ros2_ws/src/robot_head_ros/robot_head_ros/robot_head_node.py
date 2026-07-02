import json

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, Empty, Float64, Float64MultiArray, String
from std_srvs.srv import Trigger

from robot_head_ros.bridge_client import BridgeConnectionError, RobotHeadBridgeClient


class RobotHeadRosNode(Node):
    def __init__(self):
        super().__init__("robot_head_ros_bridge")

        self.declare_parameter("bridge_host", "127.0.0.1")
        self.declare_parameter("bridge_port", 8765)
        self.declare_parameter("bridge_timeout_sec", 1.0)
        self.declare_parameter("status_rate_hz", 2.0)
        self.declare_parameter("auto_switch_to_ros", True)
        self.declare_parameter("default_face_hold_ms", 4000)
        self.declare_parameter("default_text_hold_ms", 4000)
        self.declare_parameter("default_gesture_count", 3)
        self.declare_parameter("default_gesture_hold_ms", 0)
        self.declare_parameter("oopsie_hold_ms", 5000)
        self.declare_parameter("thinking_hold_ms", 4000)

        self.client = RobotHeadBridgeClient(
            host=self.get_parameter("bridge_host").value,
            port=self.get_parameter("bridge_port").value,
            timeout_sec=self.get_parameter("bridge_timeout_sec").value,
        )
        self._last_bridge_connected = None
        self._ros_mode_requested = False

        command_qos = QoSProfile(depth=10)
        command_qos.reliability = ReliabilityPolicy.RELIABLE

        self.create_subscription(String, "/robot_head/control_mode", self._mode_cb, command_qos)
        self.create_subscription(String, "/robot_head/face", self._face_cb, command_qos)
        self.create_subscription(String, "/robot_head/text", self._text_cb, command_qos)
        self.create_subscription(String, "/robot_head/gesture", self._gesture_cb, command_qos)
        self.create_subscription(Float64, "/robot_head/pan", self._pan_cb, command_qos)
        self.create_subscription(Float64, "/robot_head/tilt", self._tilt_cb, command_qos)
        self.create_subscription(Float64MultiArray, "/robot_head/pose", self._pose_cb, command_qos)
        self.create_subscription(Empty, "/robot_head/center", lambda _m: self._send("center"), command_qos)
        self.create_subscription(Empty, "/robot_head/stop", lambda _m: self._send("stop"), command_qos)
        self.create_subscription(Empty, "/robot_head/emergency_stop", lambda _m: self._send("emergency_stop"), command_qos)
        self.create_subscription(Empty, "/robot_head/arm_wave", lambda _m: self._send("arm_wave"), command_qos)
        self.create_subscription(Empty, "/robot_head/cancel_gesture", lambda _m: self._send("cancel_gesture"), command_qos)
        self.create_subscription(Empty, "/robot_head/oopsie_daisy", self._oopsie_cb, command_qos)
        self.create_subscription(Empty, "/robot_head/thinking", self._thinking_cb, command_qos)

        self.status_pub = self.create_publisher(String, "/robot_head/status", 10)
        self.mode_pub = self.create_publisher(String, "/robot_head/current_mode", 10)
        self.bridge_connected_pub = self.create_publisher(Bool, "/robot_head/bridge_connected", 10)
        self.serial_connected_pub = self.create_publisher(Bool, "/robot_head/serial_connected", 10)

        self._create_services()

        status_rate = max(0.2, float(self.get_parameter("status_rate_hz").value))
        self.create_timer(1.0 / status_rate, self._status_tick)
        self.get_logger().info(
            "Robot-head ROS bridge targeting {}:{}".format(
                self.client.host,
                self.client.port,
            )
        )

    @staticmethod
    def _parse_bool(token):
        token = str(token).strip().lower()
        if token in ("1", "true", "yes", "italic"):
            return True
        if token in ("0", "false", "no", "normal"):
            return False
        raise ValueError("italic must be 1/0, true/false, or italic/normal")

    def _request(self, command, args=None, log_failure=True):
        try:
            response = self.client.request(command, args=args)
            if not response.get("ok", False) and log_failure:
                self.get_logger().warning(response.get("message", "command rejected"))
            return response
        except BridgeConnectionError as exc:
            if log_failure:
                self.get_logger().warning("Pi host bridge unavailable: {}".format(exc))
            return {"ok": False, "message": str(exc)}

    def _send(self, command, args=None):
        self._request(command, args=args)

    def _mode_cb(self, msg):
        self._request("set_mode", {"mode": msg.data})

    def _face_cb(self, msg):
        parts = [part.strip() for part in str(msg.data).split(",")]
        if not parts or not parts[0] or len(parts) > 2:
            self.get_logger().warning("face payload must be FACE or FACE,hold_ms")
            return
        hold_ms = int(parts[1]) if len(parts) == 2 and parts[1] else int(
            self.get_parameter("default_face_hold_ms").value
        )
        self._request("face", {"name": parts[0], "hold_ms": max(0, hold_ms)})

    def _text_cb(self, msg):
        payload = str(msg.data).strip()
        if not payload:
            self.get_logger().warning("text payload cannot be empty")
            return

        hold_ms = int(self.get_parameter("default_text_hold_ms").value)
        italic = False
        text = payload
        if "|" in payload:
            parts = payload.split("|", 2)
            if len(parts) != 3:
                self.get_logger().warning("text payload must be text or hold_ms|italic|text")
                return
            hold_ms = max(0, int(parts[0].strip()))
            italic = self._parse_bool(parts[1])
            text = parts[2].strip()

        self._request("text", {"text": text, "hold_ms": hold_ms, "italic": italic})

    def _gesture_cb(self, msg):
        parts = [part.strip() for part in str(msg.data).split(",")]
        if not parts or not parts[0] or len(parts) > 3:
            self.get_logger().warning("gesture payload must be NAME[,count[,hold_ms]]")
            return
        count = int(self.get_parameter("default_gesture_count").value)
        hold_ms = int(self.get_parameter("default_gesture_hold_ms").value)
        if len(parts) >= 2 and parts[1]:
            count = max(1, int(parts[1]))
        if len(parts) >= 3 and parts[2]:
            hold_ms = max(0, int(parts[2]))
        self._request("gesture", {"name": parts[0], "count": count, "hold_ms": hold_ms})

    def _pan_cb(self, msg):
        self._request("pan", {"angle": float(msg.data)})

    def _tilt_cb(self, msg):
        self._request("tilt", {"angle": float(msg.data)})

    def _pose_cb(self, msg):
        if len(msg.data) < 2:
            self.get_logger().warning("/robot_head/pose requires [pan, tilt]")
            return
        self._request("pose", {"pan": float(msg.data[0]), "tilt": float(msg.data[1])})

    def _oopsie_cb(self, _msg):
        self._request(
            "oopsie_daisy",
            {"hold_ms": int(self.get_parameter("oopsie_hold_ms").value)},
        )

    def _thinking_cb(self, _msg):
        self._request(
            "thinking",
            {"hold_ms": int(self.get_parameter("thinking_hold_ms").value)},
        )

    def _status_tick(self):
        response = self._request("get_status", log_failure=False)
        connected = bool(response.get("ok", False))
        self.bridge_connected_pub.publish(Bool(data=connected))

        if self._last_bridge_connected != connected:
            self._last_bridge_connected = connected
            if connected:
                self.get_logger().info("Connected to Raspberry Pi host controller")
            else:
                self.get_logger().warning("Disconnected from Raspberry Pi host controller")

        if not connected:
            self._ros_mode_requested = False
            return

        status = response.get("result", {})
        self.status_pub.publish(String(data=json.dumps(status, sort_keys=True)))
        self.mode_pub.publish(String(data=str(status.get("mode", "UNKNOWN"))))
        self.serial_connected_pub.publish(
            Bool(data=bool(status.get("serial_connected", False)))
        )

        if bool(self.get_parameter("auto_switch_to_ros").value) and not self._ros_mode_requested:
            mode_response = self._request("set_mode", {"mode": "ROS"})
            self._ros_mode_requested = bool(mode_response.get("ok", False))

    def _trigger_callback(self, command, args=None):
        def callback(_request, response):
            result = self._request(command, args=args)
            response.success = bool(result.get("ok", False))
            response.message = str(result.get("message", ""))
            return response
        return callback

    def _create_services(self):
        services = {
            "center": ("/robot_head/center_service", None),
            "stop": ("/robot_head/stop_service", None),
            "emergency_stop": ("/robot_head/emergency_stop_service", None),
            "arm_wave": ("/robot_head/arm_wave_service", None),
            "nod": ("/robot_head/nod_service", None),
            "sunglasses_nod": ("/robot_head/sunglasses_nod_service", None),
            "sigma_nod": ("/robot_head/sigma_nod_service", None),
            "shake": ("/robot_head/shake_service", None),
            "look_around": ("/robot_head/look_around_service", None),
            "celebrate": ("/robot_head/celebrate_service", None),
            "dance": ("/robot_head/dance_service", None),
            "greet": ("/robot_head/greet_service", None),
            "daisy_dance": ("/robot_head/daisy_dance_service", None),
            "sleep": ("/robot_head/sleep_service", None),
            "wake_up": ("/robot_head/wake_up_service", None),
            "cancel_gesture": ("/robot_head/cancel_gesture_service", None),
            "oopsie_daisy": (
                "/robot_head/oopsie_daisy_service",
                {"hold_ms": int(self.get_parameter("oopsie_hold_ms").value)},
            ),
            "thinking": (
                "/robot_head/thinking_service",
                {"hold_ms": int(self.get_parameter("thinking_hold_ms").value)},
            ),
            "set_mode_ros": ("/robot_head/ros_mode_service", {"mode": "ROS"}),
            "set_mode_auto": ("/robot_head/auto_mode_service", {"mode": "AUTO"}),
            "set_mode_manual": ("/robot_head/manual_mode_service", {"mode": "MANUAL"}),
        }
        for command, (service_name, args) in services.items():
            host_command = "set_mode" if command.startswith("set_mode_") else command
            self.create_service(
                Trigger,
                service_name,
                self._trigger_callback(host_command, args=args),
            )

    def destroy_node(self):
        self.client.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RobotHeadRosNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
