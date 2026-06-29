class TargetSelector:
    def __init__(self):
        self.last_target = self._empty_target()

    def _empty_target(self):
        return {
            "valid": False,
            "target_type": "none",
            "center_norm": None,
            "error_norm": None
        }

    def _make_target(self, target_type, center_norm):
        if center_norm is None:
            return self._empty_target()

        x, y = center_norm

        return {
            "valid": True,
            "target_type": target_type,
            "center_norm": (x, y),
            "error_norm": (x - 0.5, y - 0.5)
        }

    def select(self, human_result=None, emotion_result=None):
        # Priority:
        # 1) full torso
        # 2) upper body
        # 3) body bbox center
        # 4) face fallback
        # 5) emotion detector face
        #
        # For head-mounted camera, upper body is important because
        # hips/torso may not always be visible when the camera is close.

        if human_result is not None and human_result.get("human_detected", False):
            torso_center_norm = human_result.get("torso_center_norm", None)

            if torso_center_norm is not None:
                self.last_target = self._make_target(
                    "torso",
                    torso_center_norm
                )
                return self.last_target

            upper_body_center_norm = human_result.get("upper_body_center_norm", None)

            if upper_body_center_norm is not None:
                self.last_target = self._make_target(
                    "upper_body",
                    upper_body_center_norm
                )
                return self.last_target

            body_center_norm = human_result.get("body_center_norm", None)

            if body_center_norm is not None:
                self.last_target = self._make_target(
                    "body",
                    body_center_norm
                )
                return self.last_target

            face_center_norm = human_result.get("face_center_norm", None)

            if face_center_norm is not None:
                self.last_target = self._make_target(
                    "face_fallback",
                    face_center_norm
                )
                return self.last_target

        if emotion_result is not None and emotion_result.get("face_detected", False):
            face_center_norm = emotion_result.get("face_center_norm", None)

            if face_center_norm is not None:
                self.last_target = self._make_target(
                    "emotion_face",
                    face_center_norm
                )
                return self.last_target

        self.last_target = self._empty_target()
        return self.last_target