import math

from control.smoothing import clamp, LowPassFilter, RateLimiter


class HeadAngleMapper:
    def __init__(
        self,
        camera_mount_mode="fixed",
        frame_width=1280,
        horizontal_fov_deg=95.0,
        center_angle=90.0,
        min_angle=0.0,
        max_angle=180.0,
        soft_limit_from_center_deg=55.0,
        servo_direction=1,
        control_reverse_x=False,
        deadband_norm=0.04,
        error_smoothing_alpha=0.35,
        max_target_step_per_update=1.2,

        # Used only for head-mounted camera
        head_mounted_gain=0.22,
        head_mounted_min_step_deg=0.30,
        head_mounted_max_step_deg=1.30,

        # Kept for compatibility with older main.py calls.
        head_mounted_kp=None,
        head_mounted_kd=None,
        head_mounted_max_delta_deg=None,
        derivative_smoothing_alpha=None
    ):
        self.camera_mount_mode = camera_mount_mode

        self.frame_width = frame_width
        self.horizontal_fov_deg = horizontal_fov_deg

        self.center_angle = center_angle
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.soft_limit_from_center_deg = soft_limit_from_center_deg

        self.servo_direction = servo_direction
        self.control_reverse_x = control_reverse_x

        self.deadband_norm = deadband_norm

        self.current_target_angle = center_angle
        self.last_raw_angle = center_angle

        self.error_filter = LowPassFilter(
            alpha=error_smoothing_alpha,
            initial_value=0.0
        )

        self.rate_limiter = RateLimiter(
            max_step=max_target_step_per_update,
            initial_value=center_angle
        )

        self.head_mounted_gain = head_mounted_gain
        self.head_mounted_min_step_deg = head_mounted_min_step_deg
        self.head_mounted_max_step_deg = head_mounted_max_step_deg

    # =====================================================
    # Utility
    # =====================================================

    def reset_center(self):
        self.current_target_angle = self.center_angle
        self.last_raw_angle = self.center_angle
        self.error_filter.reset(0.0)
        self.rate_limiter.reset(self.center_angle)

    def toggle_servo_direction(self):
        self.servo_direction *= -1
        print("Servo direction:", self.servo_direction)

    def toggle_control_reverse_x(self):
        self.control_reverse_x = not self.control_reverse_x
        print("Control reverse X:", self.control_reverse_x)

    def get_fx_pixels(self):
        fov_rad = math.radians(self.horizontal_fov_deg)
        fx = self.frame_width / (2.0 * math.tan(fov_rad / 2.0))
        return fx

    def norm_error_to_angle_error_deg(self, error_x_norm):
        error_px = error_x_norm * self.frame_width
        fx = self.get_fx_pixels()

        angle_rad = math.atan(error_px / fx)
        return math.degrees(angle_rad)

    def _apply_angle_limits(self, angle):
        soft_min = self.center_angle - self.soft_limit_from_center_deg
        soft_max = self.center_angle + self.soft_limit_from_center_deg

        angle = clamp(angle, soft_min, soft_max)
        angle = clamp(angle, self.min_angle, self.max_angle)

        return angle

    def _hold_current(self, decision="HOLD", aligned=False):
        self.error_filter.reset(0.0)

        return {
            "target_angle": self.current_target_angle,
            "raw_angle": self.current_target_angle,
            "angle_error_deg": 0.0,
            "filtered_angle_error_deg": 0.0,
            "step_deg": 0.0,
            "decision": decision,
            "aligned": aligned,
            "servo_direction": self.servo_direction,
            "control_reverse_x": self.control_reverse_x
        }

    # =====================================================
    # Main update
    # =====================================================

    def update(self, target):
        if target is None or not target.get("valid", False):
            return self._hold_current(decision="NO TARGET", aligned=False)

        error_x_norm, _ = target["error_norm"]

        if self.control_reverse_x:
            error_x_norm *= -1.0

        # Deadband:
        # Target is close enough to center, so stop moving.
        if abs(error_x_norm) < self.deadband_norm:
            return self._hold_current(decision="BODY ALIGNED", aligned=True)

        angle_error_deg = self.norm_error_to_angle_error_deg(error_x_norm)
        filtered_angle_error_deg = self.error_filter.update(angle_error_deg)

        # =================================================
        # Fixed camera mode
        # =================================================
        if self.camera_mount_mode == "fixed":
            raw_angle = (
                self.center_angle +
                self.servo_direction * filtered_angle_error_deg
            )

            step_deg = 0.0
            decision = "MOVE RIGHT" if error_x_norm > 0 else "MOVE LEFT"
            aligned = False

        # =================================================
        # Head-mounted camera mode
        # =================================================
        elif self.camera_mount_mode == "head_mounted":
            # Direction only:
            # body center right of screen -> rotate right
            # body center left of screen  -> rotate left

            direction = 1.0 if filtered_angle_error_deg > 0 else -1.0

            abs_error_deg = abs(filtered_angle_error_deg)

            step_deg = self.head_mounted_gain * abs_error_deg

            step_deg = clamp(
                step_deg,
                self.head_mounted_min_step_deg,
                self.head_mounted_max_step_deg
            )

            raw_angle = (
                self.current_target_angle +
                self.servo_direction * direction * step_deg
            )

            decision = "HM STEP RIGHT" if direction > 0 else "HM STEP LEFT"
            aligned = False

        # =================================================
        # Unknown mode
        # =================================================
        else:
            raw_angle = self.current_target_angle
            step_deg = 0.0
            decision = "UNKNOWN CAMERA MODE"
            aligned = False

        raw_angle = self._apply_angle_limits(raw_angle)

        self.last_raw_angle = raw_angle
        self.current_target_angle = self.rate_limiter.update(raw_angle)

        return {
            "target_angle": self.current_target_angle,
            "raw_angle": raw_angle,
            "angle_error_deg": angle_error_deg,
            "filtered_angle_error_deg": filtered_angle_error_deg,
            "step_deg": step_deg,
            "decision": decision,
            "aligned": aligned,
            "servo_direction": self.servo_direction,
            "control_reverse_x": self.control_reverse_x
        }