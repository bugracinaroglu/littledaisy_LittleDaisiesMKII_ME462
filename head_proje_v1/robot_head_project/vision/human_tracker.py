import cv2
import mediapipe as mp


class HumanTracker:
    def __init__(
        self,
        detection_confidence=0.60,
        tracking_confidence=0.60
    ):
        self.mp_pose = mp.solutions.pose

        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            enable_segmentation=False,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence
        )

        self.last_result = self._empty_result()

    def _empty_result(self):
        return {
            "human_detected": False,
            "bbox": None,
            "points": {},
            "connections": [],
            "body_center": None,
            "body_center_norm": None,
            "torso_center": None,
            "torso_center_norm": None,
            "method": "none"
        }

    def _get_point(self, landmarks, landmark_id, frame_width, frame_height):
        lm = landmarks[landmark_id]

        if lm.visibility < 0.45:
            return None

        x = int(lm.x * frame_width)
        y = int(lm.y * frame_height)

        if x < 0 or x >= frame_width or y < 0 or y >= frame_height:
            return None

        return x, y

    def _to_norm(self, point, frame_width, frame_height):
        x, y = point
        return x / frame_width, y / frame_height

    def _average_points(self, points):
        valid = [p for p in points if p is not None]

        if not valid:
            return None

        x = int(sum(p[0] for p in valid) / len(valid))
        y = int(sum(p[1] for p in valid) / len(valid))

        return x, y

    def update(self, frame):
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False

        result = self.pose.process(rgb)

        if not result.pose_landmarks:
            self.last_result = self._empty_result()
            return self.last_result

        landmarks = result.pose_landmarks.landmark
        pose_ids = self.mp_pose.PoseLandmark

        keypoint_map = {
            "left_shoulder": pose_ids.LEFT_SHOULDER.value,
            "right_shoulder": pose_ids.RIGHT_SHOULDER.value,
            "left_elbow": pose_ids.LEFT_ELBOW.value,
            "right_elbow": pose_ids.RIGHT_ELBOW.value,
            "left_wrist": pose_ids.LEFT_WRIST.value,
            "right_wrist": pose_ids.RIGHT_WRIST.value,
            "left_hip": pose_ids.LEFT_HIP.value,
            "right_hip": pose_ids.RIGHT_HIP.value,
            "left_knee": pose_ids.LEFT_KNEE.value,
            "right_knee": pose_ids.RIGHT_KNEE.value,
        }

        points = {}

        for name, idx in keypoint_map.items():
            point = self._get_point(landmarks, idx, w, h)

            if point is not None:
                points[name] = point

        visible_points = []

        for lm in landmarks:
            if lm.visibility > 0.45:
                x = int(lm.x * w)
                y = int(lm.y * h)

                if 0 <= x < w and 0 <= y < h:
                    visible_points.append((x, y))

        if len(visible_points) < 3:
            self.last_result = self._empty_result()
            return self.last_result

        xs = [p[0] for p in visible_points]
        ys = [p[1] for p in visible_points]

        margin = 40

        x1 = max(min(xs) - margin, 0)
        y1 = max(min(ys) - margin, 0)
        x2 = min(max(xs) + margin, w - 1)
        y2 = min(max(ys) + margin, h - 1)

        bbox = (x1, y1, x2, y2)

        body_center = (
            int((x1 + x2) / 2),
            int((y1 + y2) / 2)
        )

        body_center_norm = self._to_norm(body_center, w, h)

        torso_center = self._average_points([
            points.get("left_shoulder"),
            points.get("right_shoulder"),
            points.get("left_hip"),
            points.get("right_hip")
        ])

        if torso_center is not None:
            torso_center_norm = self._to_norm(torso_center, w, h)
        else:
            torso_center_norm = None

        connections = [
            ("left_shoulder", "right_shoulder"),
            ("left_shoulder", "left_elbow"),
            ("left_elbow", "left_wrist"),
            ("right_shoulder", "right_elbow"),
            ("right_elbow", "right_wrist"),
            ("left_shoulder", "left_hip"),
            ("right_shoulder", "right_hip"),
            ("left_hip", "right_hip"),
            ("left_hip", "left_knee"),
            ("right_hip", "right_knee"),
        ]

        self.last_result = {
            "human_detected": True,
            "bbox": bbox,
            "points": points,
            "connections": connections,
            "body_center": body_center,
            "body_center_norm": body_center_norm,
            "torso_center": torso_center,
            "torso_center_norm": torso_center_norm,
            "method": "mediapipe_pose"
        }

        return self.last_result

    def close(self):
        self.pose.close()