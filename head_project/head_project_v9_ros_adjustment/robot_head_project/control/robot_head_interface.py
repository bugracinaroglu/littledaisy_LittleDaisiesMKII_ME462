from control.control_mode import ControlMode


class RobotHeadInterface:
    """
    Mode-aware high-level robot API.

    AUTO commands are accepted only in AUTO mode, MANUAL commands only in
    MANUAL mode, and ROS commands only in ROS mode. This prevents camera
    tracking, keyboard/direct Python commands, and ROS2 callbacks from
    overwriting one another.
    """

    def __init__(
        self,
        command_sender,
        mode_manager,
        supported_faces,
        pan_min_angle,
        pan_max_angle,
        tilt_min_angle,
        tilt_max_angle,
        pan_center_angle,
        tilt_center_angle,
    ):
        self.command_sender = command_sender
        self.mode_manager = mode_manager
        self.supported_faces = {
            str(face).strip().upper() for face in supported_faces
        }

        self.pan_min_angle = float(pan_min_angle)
        self.pan_max_angle = float(pan_max_angle)
        self.tilt_min_angle = float(tilt_min_angle)
        self.tilt_max_angle = float(tilt_max_angle)
        self.pan_center_angle = float(pan_center_angle)
        self.tilt_center_angle = float(tilt_center_angle)

        self.last_pan_angle = None
        self.last_tilt_angle = None
        self.last_face = None
        self.last_command = None
        self.last_source = None
        self.last_command_sent = False

    @staticmethod
    def _clamp(value, minimum, maximum):
        value = float(value)
        return max(minimum, min(value, maximum))

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

        # AUTO tracking is rate/change limited. Explicit MANUAL and ROS
        # commands are forced so a requested target is never discarded.
        force = source != ControlMode.AUTO
        sent = self.command_sender.send_head_pose(
            pan_angle,
            tilt_angle,
            force=force,
        )
        if sent:
            self.last_pan_angle = pan_angle
            self.last_tilt_angle = tilt_angle

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
        return self._record("HEAD_TILT", source, sent)

    def show_face(self, face_name, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False

        face_name = str(face_name).strip().upper()
        if face_name not in self.supported_faces:
            print("[Face command rejected] Unsupported face:", face_name)
            return self._record("FACE", source, False)

        sent = self.command_sender.send_face(face_name)
        if sent:
            self.last_face = face_name
        return self._record("FACE", source, sent)

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
        return self._record("CENTER", source, sent)

    def stop(self, source=ControlMode.MANUAL):
        allowed, source = self._source_allowed(source)
        if not allowed:
            return False
        sent = self.command_sender.send_stop()
        return self._record("STOP", source, sent)

    def emergency_stop(self):
        """Always forward STOP, independent of the active command mode."""
        sent = self.command_sender.send_stop()
        return self._record("EMERGENCY_STOP", "SYSTEM", sent)

    def get_status(self):
        return {
            "mode": self.mode_manager.get_mode(),
            "last_pan_angle": self.last_pan_angle,
            "last_tilt_angle": self.last_tilt_angle,
            "last_face": self.last_face,
            "last_command": self.last_command,
            "last_source": self.last_source,
            "last_command_sent": self.last_command_sent,
        }
