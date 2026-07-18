from control.smoothing import LowPassFilter


class TargetSelector:
    """Select one gaze point for both pan and tilt.

    Fixed-camera priority is deliberately head-first:
    eyes, nose, pose face centre, emotion face, ears, shoulders, upper body,
    torso, and finally the complete body centre.
    """

    def __init__(self, smoothing_alpha=0.35):
        self.x_filter = LowPassFilter(alpha=smoothing_alpha, initial_value=0.5)
        self.y_filter = LowPassFilter(alpha=smoothing_alpha, initial_value=0.5)
        self.last_target = self._empty_target()
        self.last_source = None

    @staticmethod
    def _empty_target():
        return {
            "valid": False,
            "target_type": "none",
            "center_norm": None,
            "error_norm": None,
        }

    def _make_target(self, target_type, center_norm):
        if center_norm is None:
            return self._empty_target()

        x = max(0.0, min(float(center_norm[0]), 1.0))
        y = max(0.0, min(float(center_norm[1]), 1.0))

        # Reset when the source changes so a face/torso transition does not drag
        # the target across the image for many frames.
        if target_type != self.last_source:
            self.x_filter.reset(x)
            self.y_filter.reset(y)
            self.last_source = target_type

        filtered_x = self.x_filter.update(x)
        filtered_y = self.y_filter.update(y)

        return {
            "valid": True,
            "target_type": target_type,
            "center_norm": (filtered_x, filtered_y),
            "raw_center_norm": (x, y),
            "error_norm": (filtered_x - 0.5, filtered_y - 0.5),
        }

    def select(self, human_result=None, emotion_result=None):
        candidates = []

        if human_result is not None and human_result.get("human_detected", False):
            candidates.extend(
                [
                    ("eyes", human_result.get("eyes_center_norm")),
                    ("nose", human_result.get("nose_center_norm")),
                    ("pose_face", human_result.get("face_center_norm")),
                ]
            )

        if emotion_result is not None and emotion_result.get("face_detected", False):
            candidates.append(
                ("emotion_face", emotion_result.get("face_center_norm"))
            )

        if human_result is not None and human_result.get("human_detected", False):
            candidates.extend(
                [
                    ("ears", human_result.get("ears_center_norm")),
                    ("shoulders", human_result.get("shoulder_center_norm")),
                    ("upper_body", human_result.get("upper_body_center_norm")),
                    ("torso", human_result.get("torso_center_norm")),
                    ("body", human_result.get("body_center_norm")),
                ]
            )

        for target_type, center_norm in candidates:
            if center_norm is not None:
                self.last_target = self._make_target(target_type, center_norm)
                return self.last_target

        self.last_source = None
        self.last_target = self._empty_target()
        return self.last_target
