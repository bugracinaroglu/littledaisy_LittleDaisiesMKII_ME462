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
        deadband_norm=0.04,
        error_smoothing_alpha=0.75,
        max_target_step_per_update=2.0
    ):
        self.camera_mount_mode = camera_mount_mode

        self.frame_width = frame_width
        self.horizontal_fov_deg = horizontal_fov_deg

        self.center_angle = center_angle
        self.min_angle = min_angle
        self.max_angle = max_angle
        self.soft_limit_from_center_deg = soft_limit_from_center_deg

        self.servo_direction = servo_direction
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

    def reset_center(self):
        self.current_target_angle = self.center_angle
        self.last_raw_angle = self.center_angle
        self.error_filter.reset(0.0)
        self.rate_limiter.reset(self.center_angle)

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

    def update(self, target):
        if target is None or not target.get("valid", False):
            # Do not jump when target is lost.
            # Keep current angle.
            self.error_filter.update(0.0)

            return {
                "target_angle": self.current_target_angle,
                "raw_angle": self.last_raw_angle,
                "angle_error_deg": 0.0,
                "filtered_angle_error_deg": self.error_filter.value,
                "decision": "NO TARGET",
                "aligned": False
            }

        error_x_norm, _ = target["error_norm"]

        if abs(error_x_norm) < self.deadband_norm:
            angle_error_deg = 0.0
            decision = "BODY ALIGNED"
            aligned = True
        else:
            angle_error_deg = self.norm_error_to_angle_error_deg(error_x_norm)
            decision = "MOVE RIGHT" if error_x_norm > 0 else "MOVE LEFT"
            aligned = False

        filtered_angle_error_deg = self.error_filter.update(angle_error_deg)

        if self.camera_mount_mode == "fixed":
            raw_angle = (
                self.center_angle +
                self.servo_direction * filtered_angle_error_deg
            )

        elif self.camera_mount_mode == "head_mounted":
            raw_angle = (
                self.current_target_angle +
                self.servo_direction * filtered_angle_error_deg
            )

        else:
            raw_angle = self.current_target_angle
            decision = "UNKNOWN CAMERA MODE"

        raw_angle = self._apply_angle_limits(raw_angle)

        self.last_raw_angle = raw_angle
        self.current_target_angle = self.rate_limiter.update(raw_angle)

        return {
            "target_angle": self.current_target_angle,
            "raw_angle": raw_angle,
            "angle_error_deg": angle_error_deg,
            "filtered_angle_error_deg": filtered_angle_error_deg,
            "decision": decision,
            "aligned": aligned
        }