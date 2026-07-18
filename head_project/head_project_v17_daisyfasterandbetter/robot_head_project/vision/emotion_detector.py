import cv2
import numpy as np

class EmotionDetector:
    def __init__(
        self,
        model_path,
        analyze_every_n_frames=10
    ):
        self.analyze_every_n_frames = analyze_every_n_frames
        self.frame_count = 0
        self.last_result = self._empty_result()
        
        self.labels = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
        
        try:
            self.net = cv2.dnn.readNetFromONNX(model_path)
            self.net_ok = True
            print(f"[EmotionDetector] Successfully loaded ONNX model: {model_path}")
        except Exception as e:
            print(f"[Emotion init error] Failed to load ONNX model: {e}")
            self.net = None
            self.net_ok = False

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

    def update(self, frame, face_bbox=None):
        self.frame_count += 1

        if self.frame_count % self.analyze_every_n_frames != 0:
            return self.last_result
            
        if not self.net_ok:
            return self.last_result

        try:
            x1, y1, x2, y2 = 0, 0, 0, 0
            is_cropped = False
            region = None

            if face_bbox is not None:
                x1, y1, x2, y2 = face_bbox
                h, w = frame.shape[:2]
                x1, y1 = max(0, int(x1)), max(0, int(y1))
                x2, y2 = min(w, int(x2)), min(h, int(y2))
                
                # Ensure the crop is valid and has some size
                if x2 - x1 > 20 and y2 - y1 > 20:
                    analyze_frame = frame[y1:y2, x1:x2]
                    is_cropped = True
                    region = {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}
            
            if not is_cropped:
                self.last_result = self._empty_result()
                return self.last_result

            # 1. Grayscale conversion
            gray = cv2.cvtColor(analyze_frame, cv2.COLOR_BGR2GRAY)
            
            # 2. Resize to 48x48
            gray_resized = cv2.resize(gray, (48, 48))
            
            # 3. Create blob (scaling 1.0/255.0 to match Keras model input scaling)
            blob = cv2.dnn.blobFromImage(
                gray_resized, 
                scalefactor=1.0 / 255.0, 
                size=(48, 48), 
                mean=(0, 0, 0), 
                swapRB=False, 
                crop=False
            )
            
            # 4. Infer
            self.net.setInput(blob)
            preds = self.net.forward()
            
            # preds shape is (1, 7)
            probs = preds[0]
            
            emotion_scores = {}
            for i, label in enumerate(self.labels):
                emotion_scores[label] = float(probs[i] * 100.0)
            
            max_idx = np.argmax(probs)
            dominant = self.labels[max_idx]

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