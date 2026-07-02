from servo_controller import ServoController


class HeadController:
    """Two-axis controller for a fixed-camera robot head.

    Command semantics:
      * pan_angle is the desired physical HEAD angle, centred at 90 degrees.
      * tilt_angle is the physical TILT SERVO angle.

    The pan axis has an external gear pair. The RP2350 converts the requested
    head angle to a servo angle around their neutral positions using the
    configured gear ratio and direction, then applies the servo limits.
    """

    def __init__(
        self,
        pan_pin,
        tilt_pin,
        pan_enabled=True,
        tilt_enabled=True,
        freq=50,
        min_us=500,
        max_us=2500,
        max_angle=180,
        pan_head_neutral_angle=90.0,
        pan_command_min_angle=0.0,
        pan_command_max_angle=180.0,
        pan_servo_neutral_angle=90.0,
        pan_min_limit_angle=0.0,
        pan_max_limit_angle=180.0,
        pan_gear_ratio=1.7,
        pan_gear_reverses_direction=True,
        pan_step_deg=1.0,
        pan_move_interval_ms=20,
        pan_max_speed_deg_s=None,
        pan_acceleration_deg_s2=None,
        tilt_neutral_angle=90.0,
        tilt_min_limit_angle=73.0,
        tilt_max_limit_angle=105.0,
        tilt_step_deg=1.0,
        tilt_move_interval_ms=20,
        tilt_max_speed_deg_s=None,
        tilt_acceleration_deg_s2=None,
    ):
        self.pan_head_neutral_angle = float(pan_head_neutral_angle)
        self.pan_command_min_angle = float(pan_command_min_angle)
        self.pan_command_max_angle = float(pan_command_max_angle)
        self.pan_servo_neutral_angle = float(pan_servo_neutral_angle)
        self.pan_min_limit_angle = float(pan_min_limit_angle)
        self.pan_max_limit_angle = float(pan_max_limit_angle)
        self.pan_gear_ratio = float(pan_gear_ratio)
        self.pan_gear_reverses_direction = bool(
            pan_gear_reverses_direction
        )

        self.tilt_neutral_angle = float(tilt_neutral_angle)
        self.tilt_min_limit_angle = float(tilt_min_limit_angle)
        self.tilt_max_limit_angle = float(tilt_max_limit_angle)

        if self.pan_gear_ratio <= 0.0:
            raise ValueError("pan_gear_ratio must be greater than zero")

        self.pan_servo = ServoController(
            pin=pan_pin,
            enabled=pan_enabled,
            freq=freq,
            min_us=min_us,
            max_us=max_us,
            max_angle=max_angle,
            neutral_angle=self.pan_servo_neutral_angle,
            min_limit_angle=self.pan_min_limit_angle,
            max_limit_angle=self.pan_max_limit_angle,
            step_deg=pan_step_deg,
            move_interval_ms=pan_move_interval_ms,
            max_speed_deg_s=pan_max_speed_deg_s,
            acceleration_deg_s2=pan_acceleration_deg_s2,
        )

        self.tilt_servo = ServoController(
            pin=tilt_pin,
            enabled=tilt_enabled,
            freq=freq,
            min_us=min_us,
            max_us=max_us,
            max_angle=max_angle,
            neutral_angle=self.tilt_neutral_angle,
            min_limit_angle=self.tilt_min_limit_angle,
            max_limit_angle=self.tilt_max_limit_angle,
            step_deg=tilt_step_deg,
            move_interval_ms=tilt_move_interval_ms,
            max_speed_deg_s=tilt_max_speed_deg_s,
            acceleration_deg_s2=tilt_acceleration_deg_s2,
        )

    @staticmethod
    def _clamp(value, minimum, maximum):
        return max(minimum, min(value, maximum))

    def head_pan_to_servo_angle(self, head_angle):
        """Convert a desired head angle to the geared pan-servo angle.

        General form:
            servo = servo_neutral + direction * ratio * (head - head_neutral)

        The formula is applied to the offset from neutral, not to the absolute
        angle. Both the requested head command and final servo command are
        clamped to their configured limits.
        """
        head_angle = self._clamp(
            float(head_angle),
            self.pan_command_min_angle,
            self.pan_command_max_angle,
        )
        head_offset = head_angle - self.pan_head_neutral_angle
        direction = -1.0 if self.pan_gear_reverses_direction else 1.0

        servo_angle = (
            self.pan_servo_neutral_angle
            + direction * self.pan_gear_ratio * head_offset
        )
        return self._clamp(
            servo_angle,
            self.pan_min_limit_angle,
            self.pan_max_limit_angle,
        )

    def servo_pan_to_head_angle(self, servo_angle):
        """Inverse of head_pan_to_servo_angle for gesture start positions."""
        direction = -1.0 if self.pan_gear_reverses_direction else 1.0
        head_angle = self.pan_head_neutral_angle + (
            (float(servo_angle) - self.pan_servo_neutral_angle)
            / (direction * self.pan_gear_ratio)
        )
        return self.clamp_pan_head_angle(head_angle)

    def get_reachable_pan_head_limits(self):
        """Return the physical head-angle range allowed by servo and gears."""
        first = self.servo_pan_to_head_angle(self.pan_min_limit_angle)
        second = self.servo_pan_to_head_angle(self.pan_max_limit_angle)
        return min(first, second), max(first, second)

    def get_reachable_pan_head_min_angle(self):
        return self.get_reachable_pan_head_limits()[0]

    def get_reachable_pan_head_max_angle(self):
        return self.get_reachable_pan_head_limits()[1]

    def clamp_pan_head_angle(self, angle):
        return self._clamp(
            float(angle),
            self.pan_command_min_angle,
            self.pan_command_max_angle,
        )

    def clamp_tilt_angle(self, angle):
        return self._clamp(
            float(angle),
            self.tilt_min_limit_angle,
            self.tilt_max_limit_angle,
        )

    def get_current_pan_head_angle(self):
        return self.servo_pan_to_head_angle(self.pan_servo.current_angle)

    def get_target_pan_head_angle(self):
        return self.servo_pan_to_head_angle(self.pan_servo.target_angle)

    def get_current_tilt_angle(self):
        return float(self.tilt_servo.current_angle)

    def get_target_tilt_angle(self):
        return float(self.tilt_servo.target_angle)

    def is_pan_at_target(self, tolerance=1.0):
        return self.pan_servo.is_at_target(tolerance)

    def is_tilt_at_target(self, tolerance=1.0):
        return self.tilt_servo.is_at_target(tolerance)

    def is_at_target(self, tolerance=1.0):
        return (
            self.is_pan_at_target(tolerance)
            and self.is_tilt_at_target(tolerance)
        )

    def set_pose(self, pan_angle, tilt_angle):
        pan_servo_angle = self.head_pan_to_servo_angle(pan_angle)
        self.pan_servo.set_target_angle(pan_servo_angle)
        self.tilt_servo.set_target_angle(tilt_angle)

    def set_pan(self, pan_angle):
        pan_servo_angle = self.head_pan_to_servo_angle(pan_angle)
        self.pan_servo.set_target_angle(pan_servo_angle)

    def set_tilt(self, tilt_angle):
        self.tilt_servo.set_target_angle(tilt_angle)

    def center(self):
        self.pan_servo.go_to_neutral()
        self.tilt_servo.go_to_neutral()

    def stop(self):
        self.pan_servo.hold_current_position()
        self.tilt_servo.hold_current_position()

    def update(self):
        self.pan_servo.update()
        self.tilt_servo.update()

    def deinit(self):
        self.pan_servo.deinit()
        self.tilt_servo.deinit()
