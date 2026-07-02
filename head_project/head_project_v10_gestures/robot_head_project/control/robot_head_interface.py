from control.control_mode import ControlMode


class RobotHeadInterface:
    """Mode-aware high-level robot API.

    Direct/manual examples after selecting MANUAL mode::

        robot_head.show_face("SIGMA", hold_ms=4000)
        robot_head.nod_head(count=2)
        robot_head.sunglasses_nod(count=2, hold_ms=4000)
        robot_head.sigma_nod(count=3, hold_ms=5000)
        robot_head.shake_head(count=2)
        robot_head.look_around(count=1)
        robot_head.celebrate(count=2, hold_ms=3000)
        robot_head.cancel_gesture()

    AUTO, MANUAL and ROS sources are accepted only while their corresponding
    control mode is active. This prevents controllers from overwriting each
    other. Gesture timing and servo sequencing are executed on the RP2350.
    """

    def __init__(
        self,
        command_sender,
        mode_manager,
        supported_faces,
        supported_gestures,
        pan_min_angle,
        pan_max_angle,
        tilt_min_angle,
        tilt_max_angle,
        pan_center_angle,
        tilt_center_angle,
        default_gesture_count=2,
        max_gesture_count=8,
        default_gesture_hold_ms=0,
    ):
        self.command_sender = command_sender
        self.mode_manager = mode_manager
        self.supported_faces = {
            str(face).strip().upper() for face in supported_faces
        }
        self.supported_gestures = {
            str(gesture).strip().upper() for gesture in supported_gestures
        }

        self.pan_min_angle = float(pan_min_angle)
        self.pan_max_angle = float(pan_max_angle)
        self.tilt_min_angle = float(tilt_min_angle)
        self.tilt_max_angle = float(tilt_max_angle)
        self.pan_center_angle = float(pan_center_angle)
        self.tilt_center_angle = float(tilt_center_angle)

        self.default_gesture_count = max(1, int(default_gesture_count))
        self.max_gesture_count = max(1, int(max_gesture_count))
        self.default_gesture_hold_ms = max(0, int(default_gesture_hold_ms))

        self.last_pan_angle = None
        self.last_tilt_angle = None
        self.last_face = None
        self.last_gesture = None
        self.last_command = None
        self.last_source = None
        self.last_command_sent = False

    @staticmethod
    def _clamp(value, minimum, maximum):
        value = float(value)
        return max(minimum, min(value, maximum))

    @staticmethod
    def _normalize_hold_ms(hold_ms):
        if hold_ms is None:
            return None
        return max(0, int(hold_ms))

    def _normalize_gesture_count(self, count):
        if count is None:
            count = self.default_gesture_count
        return max(1, min(int(count), self.max_gesture_count))

    def _source_allowed(self, source):
        source = ControlMode.normalize(source)
        allowed = self.mode_manager.can_execute(source)
        if not allowed:
            print(
                "[Command blocked] source={} active_mode={}".format(
                    source,
                    self.mode_manager.get_mode(),
                )
            )
        return allowed, source

    def _record(self, command, source, sent):
        self.last_command = command
        self.last_source = source
        self.last_command_sent = bool(sent)
        return bool(sent)

    def set_head_pose(self, pan_angle, tilt_angle, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False

        pan_angle = self._clamp(
            pan_angle,
            self.pan_min_angle,
            self.pan_max_angle,
        )
        tilt_angle = self._clamp(
            tilt_angle,
            self.tilt_min_angle,
            self.tilt_max_angle,
        )

        force = source != ControlMode.AUTO
        sent = self.command_sender.send_head_pose(
            pan_angle,
            tilt_angle,
            force=force,
        )
        if sent:
            self.last_pan_angle = pan_angle
            self.last_tilt_angle = tilt_angle
            self.last_gesture = None
        return self._record("HEAD_POSE", source, sent)

    def set_pan(self, pan_angle, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False

        pan_angle = self._clamp(
            pan_angle,
            self.pan_min_angle,
            self.pan_max_angle,
        )
        sent = self.command_sender.send_head_pan(pan_angle)
        if sent:
            self.last_pan_angle = pan_angle
            self.last_gesture = None
        return self._record("HEAD_PAN", source, sent)

    def set_tilt(self, tilt_angle, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False

        tilt_angle = self._clamp(
            tilt_angle,
            self.tilt_min_angle,
            self.tilt_max_angle,
        )
        sent = self.command_sender.send_head_tilt(tilt_angle)
        if sent:
            self.last_tilt_angle = tilt_angle
            self.last_gesture = None
        return self._record("HEAD_TILT", source, sent)

    def show_face(
        self,
        face_name,
        hold_ms=0,
        source=ControlMode.MANUAL,
    ):
        """Show a face; hold_ms blocks RP2350 IMU face overrides temporarily."""
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False

        face_name = str(face_name).strip().upper()
        if face_name not in self.supported_faces:
            print("[Face command rejected] Unsupported face:", face_name)
            return self._record("FACE", source, False)

        hold_ms = self._normalize_hold_ms(hold_ms)
        if hold_ms is None:
            hold_ms = 0
        sent = self.command_sender.send_face(face_name, hold_ms=hold_ms)
        if sent:
            # The RP2350 intentionally renders NEUTRAL as CURIOUS.
            self.last_face = "CURIOUS" if face_name == "NEUTRAL" else face_name
        return self._record("FACE:{}".format(face_name), source, sent)

    def play_gesture(
        self,
        gesture_name,
        count=None,
        hold_ms=None,
        source=ControlMode.MANUAL,
    ):
        """Run a named RP2350 gesture with configurable repeats and face lock."""
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False

        gesture_name = str(gesture_name).strip().upper()
        if gesture_name not in self.supported_gestures:
            print("[Gesture rejected] Unsupported gesture:", gesture_name)
            return self._record("GESTURE", source, False)

        count = self._normalize_gesture_count(count)
        if hold_ms is None:
            hold_ms = self.default_gesture_hold_ms
        hold_ms = max(0, int(hold_ms))

        sent = self.command_sender.send_gesture(
            gesture_name,
            count=count,
            hold_ms=hold_ms,
        )
        if sent:
            self.last_gesture = gesture_name
            face_by_gesture = {
                "SUNGLASSES_NOD": "SUNGLASSES",
                "SIGMA_NOD": "SIGMA",
                "LOOK_AROUND": "CURIOUS",
                "CELEBRATE": "HAPPY",
                "SLEEP": "SLEEPING",
                "WAKE_UP": "CURIOUS",
            }
            if gesture_name in face_by_gesture:
                self.last_face = face_by_gesture[gesture_name]
        return self._record(
            "GESTURE:{} x{} hold={}ms".format(
                gesture_name,
                count,
                hold_ms,
            ),
            source,
            sent,
        )

    def nod_head(self, count=None, hold_ms=0, source=ControlMode.MANUAL):
        return self.play_gesture("NOD", count, hold_ms, source)

    def sunglasses_nod(
        self,
        count=None,
        hold_ms=0,
        source=ControlMode.MANUAL,
    ):
        return self.play_gesture("SUNGLASSES_NOD", count, hold_ms, source)

    def sigma_nod(
        self,
        count=None,
        hold_ms=0,
        source=ControlMode.MANUAL,
    ):
        return self.play_gesture("SIGMA_NOD", count, hold_ms, source)

    def shake_head(self, count=None, hold_ms=0, source=ControlMode.MANUAL):
        return self.play_gesture("SHAKE", count, hold_ms, source)

    def look_around(self, count=1, hold_ms=0, source=ControlMode.MANUAL):
        return self.play_gesture("LOOK_AROUND", count, hold_ms, source)

    def celebrate(self, count=None, hold_ms=0, source=ControlMode.MANUAL):
        return self.play_gesture("CELEBRATE", count, hold_ms, source)

    def sleep(self, hold_ms=0, source=ControlMode.MANUAL):
        return self.play_gesture("SLEEP", 1, hold_ms, source)

    def wake_up(self, hold_ms=0, source=ControlMode.MANUAL):
        return self.play_gesture("WAKE_UP", 1, hold_ms, source)

    def cancel_gesture(self, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False
        sent = self.command_sender.send_cancel_gesture()
        if sent:
            self.last_gesture = None
        return self._record("GESTURE:CANCEL", source, sent)

    def wave_arm(self, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False
        sent = self.command_sender.send_arm_wave()
        return self._record("ARM_WAVE", source, sent)

    def center(self, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False

        sent = self.command_sender.send_center()
        if sent:
            self.last_pan_angle = self.pan_center_angle
            self.last_tilt_angle = self.tilt_center_angle
            self.last_face = "CURIOUS"
            self.last_gesture = None
        return self._record("CENTER", source, sent)

    def stop(self, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False
        sent = self.command_sender.send_stop()
        if sent:
            self.last_gesture = None
        return self._record("STOP", source, sent)

    def emergency_stop(self):
        """Always forward STOP, independent of the active command mode."""
        sent = self.command_sender.send_stop()
        if sent:
            self.last_gesture = None
        return self._record("EMERGENCY_STOP", "SYSTEM", sent)

    def get_status(self):
        return {
            "mode": self.mode_manager.get_mode(),
            "last_pan_angle": self.last_pan_angle,
            "last_tilt_angle": self.last_tilt_angle,
            "last_face": self.last_face,
            "last_gesture": self.last_gesture,
            "last_command": self.last_command,
            "last_source": self.last_source,
            "last_command_sent": self.last_command_sent,
        }
