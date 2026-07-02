import math

from control.smoothing import LowPassFilter, clamp


class TargetDistanceEstimator:
    """Simple monocular target-distance estimate.

    The estimate is only used to compensate the small camera-to-head offset.
    It is intentionally lightweight: shoulder width first, face width second,
    and a fixed-distance fallback when neither measurement is reliable.
    """

    def __init__(
        self,
        mode="auto",
        assumed_shoulder_width_m=0.40,
        assumed_face_width_m=0.16,
        default_distance_m=2.0,
        min_distance_m=0.5,
        max_distance_m=6.0,
        smoothing_alpha=0.20,
        max_change_per_frame_m=0.30,
        min_shoulder_width_pixels=35.0,
        min_face_width_pixels=30.0,
    ):
        self.mode = str(mode).lower()
        self.assumed_shoulder_width_m = float(assumed_shoulder_width_m)
        self.assumed_face_width_m = float(assumed_face_width_m)
        self.default_distance_m = float(default_distance_m)
        self.min_distance_m = float(min_distance_m)
        self.max_distance_m = float(max_distance_m)
        self.max_change_per_frame_m = float(max_change_per_frame_m)
        self.min_shoulder_width_pixels = float(min_shoulder_width_pixels)
        self.min_face_width_pixels = float(min_face_width_pixels)

        self.filter = LowPassFilter(
            alpha=smoothing_alpha,
            initial_value=self.default_distance_m,
        )
        self.last_distance_m = self.default_distance_m

    @staticmethod
    def _point_distance(point_a, point_b):
        if point_a is None or point_b is None:
            return None
        return math.hypot(
            point_a[0] - point_b[0], point_a[1] - point_b[1]
        )

    @staticmethod
    def _bbox_width(bbox):
        if bbox is None:
            return None
        return max(0.0, float(bbox[2] - bbox[0]))

    def _distance_from_shoulder(self, human_result, fx_pixels):
        if human_result is None:
            return None

        points = human_result.get("points", {})
        pixel_width = self._point_distance(
            points.get("left_shoulder"),
            points.get("right_shoulder"),
        )
        if pixel_width is None or pixel_width < self.min_shoulder_width_pixels:
            return None

        distance = fx_pixels * self.assumed_shoulder_width_m / pixel_width
        return distance, "shoulder", pixel_width

    def _distance_from_face(self, human_result, emotion_result, fx_pixels):
        bbox = None
        source = None

        if human_result is not None:
            bbox = human_result.get("face_bbox")
            if bbox is not None:
                source = "pose_face"

        if bbox is None and emotion_result is not None:
            region = emotion_result.get("region")
            if region is not None:
                x = region.get("x", 0)
                y = region.get("y", 0)
                width = region.get("w", 0)
                height = region.get("h", 0)
                if width > 0 and height > 0:
                    bbox = (x, y, x + width, y + height)
                    source = "emotion_face"

        pixel_width = self._bbox_width(bbox)
        if pixel_width is None or pixel_width < self.min_face_width_pixels:
            return None

        distance = fx_pixels * self.assumed_face_width_m / pixel_width
        return distance, source, pixel_width

    def _limit_and_filter(self, measurement):
        distance = clamp(
            float(measurement), self.min_distance_m, self.max_distance_m
        )
        distance = clamp(
            distance,
            self.last_distance_m - self.max_change_per_frame_m,
            self.last_distance_m + self.max_change_per_frame_m,
        )
        filtered = self.filter.update(distance)
        filtered = clamp(filtered, self.min_distance_m, self.max_distance_m)
        self.last_distance_m = filtered
        return filtered

    def update(self, human_result, emotion_result, camera):
        fx_pixels, _ = camera.get_focal_lengths_pixels()
        if fx_pixels is None:
            return {
                "distance_m": self.default_distance_m,
                "distance_source": "fixed_no_intrinsics",
                "distance_measurement_px": None,
                "distance_valid": False,
            }

        measurement = None

        if self.mode in ("auto", "shoulder"):
            measurement = self._distance_from_shoulder(
                human_result, fx_pixels
            )

        if measurement is None and self.mode in ("auto", "face"):
            measurement = self._distance_from_face(
                human_result, emotion_result, fx_pixels
            )

        if measurement is None:
            if self.mode == "none":
                return {
                    "distance_m": None,
                    "distance_source": "none",
                    "distance_measurement_px": None,
                    "distance_valid": False,
                }

            filtered = self._limit_and_filter(self.default_distance_m)
            return {
                "distance_m": filtered,
                "distance_source": "fixed_fallback",
                "distance_measurement_px": None,
                "distance_valid": False,
            }

        raw_distance, source, measurement_pixels = measurement
        filtered = self._limit_and_filter(raw_distance)
        return {
            "distance_m": filtered,
            "raw_distance_m": raw_distance,
            "distance_source": source,
            "distance_measurement_px": measurement_pixels,
            "distance_valid": True,
        }
