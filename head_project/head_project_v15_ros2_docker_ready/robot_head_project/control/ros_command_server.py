import json
import socketserver
import threading

from control.control_mode import ControlMode


class _ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class RosCommandServer:
    """Local JSON-lines command server for the Docker ROS2 bridge.

    The Raspberry Pi OS application remains the single owner of the RP2350
    serial port. A ROS2 node running in a host-network Docker container talks
    to this server through 127.0.0.1, so Picamera2 and the GUI stay on the host.
    """

    def __init__(
        self,
        robot_head,
        mode_manager,
        command_sender,
        host="127.0.0.1",
        port=8765,
    ):
        self.robot_head = robot_head
        self.mode_manager = mode_manager
        self.command_sender = command_sender
        self.host = str(host)
        self.port = int(port)
        self.server = None
        self.thread = None
        self.available = False

    @staticmethod
    def _response(request_id, ok, message, result=None):
        payload = {
            "id": request_id,
            "ok": bool(ok),
            "message": str(message),
        }
        if result is not None:
            payload["result"] = result
        return payload

    @staticmethod
    def _as_int(value, default=None, minimum=None, maximum=None):
        if value is None:
            return default
        parsed = int(value)
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    @staticmethod
    def _as_float(value):
        return float(value)

    def _status(self):
        status = dict(self.robot_head.get_status())
        status.update(
            {
                "serial_connected": bool(self.command_sender.is_connected()),
                "command_server_available": bool(self.available),
                "command_server_host": self.host,
                "command_server_port": self.port,
            }
        )
        return status

    def _execute(self, command, args):
        command = str(command or "").strip().lower()
        args = args if isinstance(args, dict) else {}

        if command == "ping":
            return True, "pong", self._status()

        if command == "get_status":
            return True, "status", self._status()

        if command == "set_mode":
            mode = ControlMode.normalize(args.get("mode"))
            changed = self.mode_manager.set_mode(mode)
            return True, "mode set to {}".format(mode), {
                "mode": self.mode_manager.get_mode(),
                "changed": bool(changed),
            }

        if command == "face":
            ok = self.robot_head.show_face(
                args.get("name", ""),
                hold_ms=self._as_int(args.get("hold_ms"), 0, 0),
                source=ControlMode.ROS,
            )
            return ok, "face command sent" if ok else "face command blocked", None

        if command == "text":
            ok = self.robot_head.show_text(
                args.get("text", ""),
                hold_ms=self._as_int(args.get("hold_ms"), 4000, 0),
                italic=bool(args.get("italic", False)),
                source=ControlMode.ROS,
            )
            return ok, "text command sent" if ok else "text command blocked", None

        if command == "gesture":
            ok = self.robot_head.play_gesture(
                args.get("name", ""),
                count=self._as_int(args.get("count"), None, 1),
                hold_ms=self._as_int(args.get("hold_ms"), None, 0),
                source=ControlMode.ROS,
            )
            return ok, "gesture command sent" if ok else "gesture command blocked", None

        if command == "pan":
            ok = self.robot_head.set_pan(
                self._as_float(args.get("angle")),
                source=ControlMode.ROS,
            )
            return ok, "pan command sent" if ok else "pan command blocked", None

        if command == "tilt":
            ok = self.robot_head.set_tilt(
                self._as_float(args.get("angle")),
                source=ControlMode.ROS,
            )
            return ok, "tilt command sent" if ok else "tilt command blocked", None

        if command == "pose":
            ok = self.robot_head.set_head_pose(
                self._as_float(args.get("pan")),
                self._as_float(args.get("tilt")),
                source=ControlMode.ROS,
            )
            return ok, "pose command sent" if ok else "pose command blocked", None

        simple_commands = {
            "center": lambda: self.robot_head.center(source=ControlMode.ROS),
            "stop": lambda: self.robot_head.stop(source=ControlMode.ROS),
            "emergency_stop": self.robot_head.emergency_stop,
            "arm_wave": lambda: self.robot_head.wave_arm(source=ControlMode.ROS),
            "cancel_gesture": lambda: self.robot_head.cancel_gesture(source=ControlMode.ROS),
            "oopsie_daisy": lambda: self.robot_head.show_oopsie_daisy(
                hold_ms=self._as_int(args.get("hold_ms"), 5000, 0),
                source=ControlMode.ROS,
            ),
            "thinking": lambda: self.robot_head.show_thinking(
                hold_ms=self._as_int(args.get("hold_ms"), 4000, 0),
                source=ControlMode.ROS,
            ),
        }
        if command in simple_commands:
            ok = bool(simple_commands[command]())
            return ok, "{} sent".format(command) if ok else "{} blocked".format(command), None

        gesture_aliases = {
            "nod": "NOD",
            "sunglasses_nod": "SUNGLASSES_NOD",
            "sigma_nod": "SIGMA_NOD",
            "shake": "SHAKE",
            "look_around": "LOOK_AROUND",
            "celebrate": "CELEBRATE",
            "dance": "DANCE",
            "greet": "GREET",
            "daisy_dance": "DAISY_DANCE",
            "sleep": "SLEEP",
            "wake_up": "WAKE_UP",
        }
        if command in gesture_aliases:
            ok = self.robot_head.play_gesture(
                gesture_aliases[command],
                count=self._as_int(args.get("count"), None, 1),
                hold_ms=self._as_int(args.get("hold_ms"), None, 0),
                source=ControlMode.ROS,
            )
            return ok, "{} sent".format(command) if ok else "{} blocked".format(command), None

        raise ValueError("Unsupported command: {}".format(command))

    def _handle_request(self, payload):
        request_id = payload.get("id")
        try:
            ok, message, result = self._execute(
                payload.get("command"),
                payload.get("args", {}),
            )
            return self._response(request_id, ok, message, result)
        except Exception as exc:
            return self._response(request_id, False, str(exc))

    def start(self):
        if self.available:
            return True

        owner = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                while True:
                    raw = self.rfile.readline()
                    if not raw:
                        break
                    try:
                        payload = json.loads(raw.decode("utf-8"))
                        if not isinstance(payload, dict):
                            raise ValueError("request must be a JSON object")
                        response = owner._handle_request(payload)
                    except Exception as exc:
                        response = owner._response(None, False, str(exc))

                    self.wfile.write(
                        (json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8")
                    )
                    self.wfile.flush()

        try:
            self.server = _ReusableThreadingTCPServer(
                (self.host, self.port),
                Handler,
            )
            self.thread = threading.Thread(
                target=self.server.serve_forever,
                name="ros-command-server",
                daemon=True,
            )
            self.thread.start()
            self.available = True
            print(
                "ROS Docker command server listening on {}:{}".format(
                    self.host,
                    self.port,
                )
            )
            return True
        except Exception as exc:
            print("Could not start ROS Docker command server:", exc)
            self.close()
            return False

    def close(self):
        self.available = False
        if self.server is not None:
            try:
                self.server.shutdown()
            except Exception:
                pass
            try:
                self.server.server_close()
            except Exception:
                pass
            self.server = None

        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.thread = None
