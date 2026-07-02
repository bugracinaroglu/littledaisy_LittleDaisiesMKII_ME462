import math

from control.smoothing import LowPassFilter, RateLimiter, clamp


class HeadPoseMapper:
    """Convert a fixed-camera target into absolute head-pan and tilt command angles."""

    def __init__(
        self,
        camera,
        enable_tilt_tracking=True,
        head_pivot_offset_m=(0.0, -0.20, 0.0),
        camera_to_head_yaw_bias_deg=0.0,
        camera_to_head_pitch_bias_deg=0.0,
        pan_center_angle=90.0,
        pan_min_angle=0.0,
        pan_max_angle=180.0,
        pan_soft_limit_from_center_deg=45.0,
        pan_servo_direction=1,
        control_reverse_x=False,
        tilt_center_angle=90.0,
        tilt_min_angle=73.0,
        tilt_max_angle=105.0,
        tilt_soft_limit_from_center_deg=15.0,
        tilt_servo_direction=1,
        control_reverse_y=False,
        pan_angle_deadband_deg=0.50,
        tilt_angle_deadband_deg=0.50,
        pan_smoothing_alpha=0.35,
        tilt_smoothing_alpha=0.25,
        pan_max_step_per_update_deg=2.50,
        tilt_max_step_per_update_deg=1.80,
    ):
        self.camera = camera
        self.enable_tilt_tracking = bool(enable_tilt_tracking)

        self.head_pivot_offset_x_m = float(head_pivot_offset_m[0])
        self.head_pivot_offset_y_m = float(head_pivot_offset_m[1])
        self.head_pivot_offset_z_m = float(head_pivot_offset_m[2])

        self.camera_to_head_yaw_bias_deg = float(
            camera_to_head_yaw_bias_deg
        )
        self.camera_to_head_pitch_bias_deg = float(
            camera_to_head_pitch_bias_deg
        )

        self.pan_center_angle = float(pan_center_angle)
        self.pan_min_angle = float(pan_min_angle)
        self.pan_max_angle = float(pan_max_angle)
        self.pan_soft_limit_from_center_deg = float(
            pan_soft_limit_from_center_deg
        )
        self.pan_servo_direction = 1 if pan_servo_direction >= 0 else -1
        self.control_reverse_x = bool(control_reverse_x)

        self.tilt_center_angle = float(tilt_center_angle)
        self.tilt_min_angle = float(tilt_min_angle)
        self.tilt_max_angle = float(tilt_max_angle)
        self.tilt_soft_limit_from_center_deg = float(
            tilt_soft_limit_from_center_deg
        )
        self.tilt_servo_direction = 1 if tilt_servo_direction >= 0 else -1
        self.control_reverse_y = bool(control_reverse_y)

        self.pan_angle_deadband_deg = float(pan_angle_deadband_deg)
        self.tilt_angle_deadband_deg = float(tilt_angle_deadband_deg)

        self.pan_error_filter = LowPassFilter(
            alpha=pan_smoothing_alpha,
            initial_value=0.0,
        )
        self.tilt_error_filter = LowPassFilter(
            alpha=tilt_smoothing_alpha,
            initial_value=0.0,
        )
        self.pan_rate_limiter = RateLimiter(
            max_step=pan_max_step_per_update_deg,
            initial_value=self.pan_center_angle,
        )
        self.tilt_rate_limiter = RateLimiter(
            max_step=tilt_max_step_per_update_deg,
            initial_value=self.tilt_center_angle,
        )

        self.current_pan_angle = self.pan_center_angle
        self.current_tilt_angle = self.tilt_center_angle

    # =====================================================
    # Controls
    # =====================================================

    def reset_center(self):
        self.current_pan_angle = self.pan_center_angle
        self.current_tilt_angle = self.tilt_center_angle
        self.pan_error_filter.reset(0.0)
        self.tilt_error_filter.reset(0.0)
        self.pan_rate_limiter.reset(self.pan_center_angle)
        self.tilt_rate_limiter.reset(self.tilt_center_angle)

    def toggle_pan_servo_direction(self):
        self.pan_servo_direction *= -1
        print("Pan servo direction:", self.pan_servo_direction)

    def toggle_tilt_servo_direction(self):
        self.tilt_servo_direction *= -1
        print("Tilt servo direction:", self.tilt_servo_direction)

    def toggle_control_reverse_x(self):
        self.control_reverse_x = not self.control_reverse_x
        print("Control reverse X:", self.control_reverse_x)

    def toggle_control_reverse_y(self):
        self.control_reverse_y = not self.control_reverse_y
        print("Control reverse Y:", self.control_reverse_y)

    def toggle_tilt_tracking(self):
        self.enable_tilt_tracking = not self.enable_tilt_tracking
        print("Up/down human tracking:", self.enable_tilt_tracking)

    # =====================================================
    # Geometry
    # =====================================================

    @staticmethod
    def _point_from_ray(ray, distance_m):
        ray_x, ray_y, _ = ray
        if distance_m is None:
            # Direction-only fallback. Translation compensation is skipped
            # because the ray has no metric scale.
            return ray_x, ray_y, 1.0, False

        distance_m = max(float(distance_m), 0.05)
        return ray_x * distance_m, ray_y * distance_m, distance_m, True

    def _target_vector_from_head(self, ray, distance_m):
        camera_x, camera_y, camera_z, metric = self._point_from_ray(
            ray, distance_m
        )

        if metric:
            head_x = camera_x - self.head_pivot_offset_x_m
            head_y = camera_y - self.head_pivot_offset_y_m
            head_z = camera_z - self.head_pivot_offset_z_m
        else:
            head_x, head_y, head_z = camera_x, camera_y, camera_z

        return head_x, head_y, head_z, metric

    def _geometric_angles_deg(self, ray, distance_m):
        head_x, head_y, head_z, metric = self._target_vector_from_head(
            ray, distance_m
        )

        forward_distance = math.hypot(head_x, head_z)
        pan_deg = math.degrees(math.atan2(head_x, head_z))
        tilt_deg = math.degrees(math.atan2(head_y, forward_distance))

        pan_deg += self.camera_to_head_yaw_bias_deg
        tilt_deg += self.camera_to_head_pitch_bias_deg

        if self.control_reverse_x:
            pan_deg *= -1.0
        if self.control_reverse_y:
            tilt_deg *= -1.0

        return pan_deg, tilt_deg, metric

    def _limit_pan(self, angle):
        soft_min = self.pan_center_angle - self.pan_soft_limit_from_center_deg
        soft_max = self.pan_center_angle + self.pan_soft_limit_from_center_deg
        return clamp(
            clamp(angle, soft_min, soft_max),
            self.pan_min_angle,
            self.pan_max_angle,
        )

    def _limit_tilt(self, angle):
        soft_min = self.tilt_center_angle - self.tilt_soft_limit_from_center_deg
        soft_max = self.tilt_center_angle + self.tilt_soft_limit_from_center_deg
        return clamp(
            clamp(angle, soft_min, soft_max),
            self.tilt_min_angle,
            self.tilt_max_angle,
        )

    def _hold_current(self, decision="NO TARGET"):
        return {
            "pan_angle": self.current_pan_angle,
            "tilt_angle": self.current_tilt_angle,
            "raw_pan_angle": self.current_pan_angle,
            "raw_tilt_angle": self.current_tilt_angle,
            "pan_error_deg": 0.0,
            "tilt_error_deg": 0.0,
            "filtered_pan_error_deg": 0.0,
            "filtered_tilt_error_deg": 0.0,
            "decision": decision,
            "pan_decision": "HOLD",
            "tilt_decision": "HOLD",
            "metric_offset_compensation": False,
            "pan_servo_direction": self.pan_servo_direction,
            "tilt_servo_direction": self.tilt_servo_direction,
            "control_reverse_x": self.control_reverse_x,
            "control_reverse_y": self.control_reverse_y,
            "tilt_tracking_enabled": self.enable_tilt_tracking,
        }

    # =====================================================
    # Main update
    # =====================================================

    def update(self, target):
        if target is None or not target.get("valid", False):
            return self._hold_current("NO TARGET")

        center_norm = target.get("center_norm")
        if center_norm is None:
            return self._hold_current("NO TARGET POINT")

        frame_width, frame_height = self.camera.get_output_size()
        pixel_x = center_norm[0] * (frame_width - 1)
        pixel_y = center_norm[1] * (frame_height - 1)

        ray = self.camera.pixel_to_ray(pixel_x, pixel_y)
        distance_m = target.get("distance_m")
        pan_error_deg, tilt_error_deg, metric = self._geometric_angles_deg(
            ray, distance_m
        )

        filtered_pan_error = self.pan_error_filter.update(pan_error_deg)
        filtered_tilt_error = self.tilt_error_filter.update(tilt_error_deg)

        raw_pan_angle = self._limit_pan(
            self.pan_center_angle
            + self.pan_servo_direction * filtered_pan_error
        )

        if self.enable_tilt_tracking:
            raw_tilt_angle = self._limit_tilt(
                self.tilt_center_angle
                + self.tilt_servo_direction * filtered_tilt_error
            )
        else:
            raw_tilt_angle = self.current_tilt_angle

        if (
            abs(raw_pan_angle - self.current_pan_angle)
            < self.pan_angle_deadband_deg
        ):
            raw_pan_angle = self.current_pan_angle
            pan_decision = "PAN HOLD"
        else:
            pan_decision = "PAN RIGHT" if pan_error_deg > 0 else "PAN LEFT"

        if not self.enable_tilt_tracking:
            tilt_decision = "TILT DISABLED"
        elif (
            abs(raw_tilt_angle - self.current_tilt_angle)
            < self.tilt_angle_deadband_deg
        ):
            raw_tilt_angle = self.current_tilt_angle
            tilt_decision = "TILT HOLD"
        else:
            tilt_decision = "TILT DOWN" if tilt_error_deg > 0 else "TILT UP"

        self.current_pan_angle = self.pan_rate_limiter.update(raw_pan_angle)
        self.current_tilt_angle = self.tilt_rate_limiter.update(raw_tilt_angle)

        return {
            "pan_angle": self.current_pan_angle,
            "tilt_angle": self.current_tilt_angle,
            "raw_pan_angle": raw_pan_angle,
            "raw_tilt_angle": raw_tilt_angle,
            "pan_error_deg": pan_error_deg,
            "tilt_error_deg": tilt_error_deg,
            "filtered_pan_error_deg": filtered_pan_error,
            "filtered_tilt_error_deg": filtered_tilt_error,
            "decision": pan_decision + " / " + tilt_decision,
            "pan_decision": pan_decision,
            "tilt_decision": tilt_decision,
            "metric_offset_compensation": metric,
            "distance_m": distance_m,
            "distance_source": target.get("distance_source", "unknown"),
            "pan_servo_direction": self.pan_servo_direction,
            "tilt_servo_direction": self.tilt_servo_direction,
            "control_reverse_x": self.control_reverse_x,
            "control_reverse_y": self.control_reverse_y,
            "tilt_tracking_enabled": self.enable_tilt_tracking,
        }
