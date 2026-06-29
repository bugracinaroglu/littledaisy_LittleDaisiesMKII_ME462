class EmotionDetector:
    def __init__(
        self,
        analyze_every_n_frames=10,
        detector_backend="opencv",
        enforce_detection=True
    ):
        from deepface import DeepFace

        self.DeepFace = DeepFace

        self.analyze_every_n_frames = analyze_every_n_frames
        self.detector_backend = detector_backend
        self.enforce_detection = enforce_detection

        self.frame_count = 0

        self.last_result = self._empty_result()

    def _empty_result(self):
        return {
            "face_detected": False,
            "dominant": "No face",
            "top_scores": [],
            "all_scores": {},
            "region": None,
            "face_center_norm": None,
            "ok": False,
            "error": None
        }

    def _face_center_from_region(self, region, frame):
        if region is None:
            return None

        h, w = frame.shape[:2]

        x = region.get("x", 0)
        y = region.get("y", 0)
        rw = region.get("w", 0)
        rh = region.get("h", 0)

        if rw <= 0 or rh <= 0:
            return None

        cx = x + rw / 2
        cy = y + rh / 2

        return cx / w, cy / h

    def update(self, frame):
        self.frame_count += 1

        if self.frame_count % self.analyze_every_n_frames != 0:
            return self.last_result

        try:
            result = self.DeepFace.analyze(
                img_path=frame,
                actions=["emotion"],
                enforce_detection=self.enforce_detection,
                detector_backend=self.detector_backend
            )

            if isinstance(result, list):
                result = result[0]

            dominant = result.get("dominant_emotion", "Unknown")
            emotion_scores = result.get("emotion", {})
            region = result.get("region", None)

            top_scores = sorted(
                emotion_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )

            face_center_norm = self._face_center_from_region(region, frame)

            self.last_result = {
                "face_detected": region is not None,
                "dominant": dominant,
                "top_scores": top_scores,
                "all_scores": emotion_scores,
                "region": region,
                "face_center_norm": face_center_norm,
                "ok": True,
                "error": None
            }

            print("\n[Emotion]")
            print("Dominant:", dominant)
            print("Scores:", emotion_scores)

        except Exception as e:
            self.last_result = {
                "face_detected": False,
                "dominant": "No face",
                "top_scores": [],
                "all_scores": {},
                "region": None,
                "face_center_norm": None,
                "ok": False,
                "error": str(e)
            }

            print("[Emotion error]:", e)

        return self.last_result