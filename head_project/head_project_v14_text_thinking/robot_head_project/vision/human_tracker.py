import cv2
import mediapipe as mp


class HumanTracker:
    def __init__(
        self,
        detection_confidence=0.70,
        tracking_confidence=0.70,
        landmark_visibility=0.45,
        strict_torso_validation=False,
        enable_face_fallback=True,
        min_body_height_ratio=0.16,
        min_body_width_ratio=0.08,
        min_upper_body_height_ratio=0.10,
        min_upper_body_width_ratio=0.08,
        min_visible_pose_points=5,
    ):
        self.landmark_visibility = float(landmark_visibility)
        self.strict_torso_validation = strict_torso_validation
        self.enable_face_fallback = enable_face_fallback
        self.min_body_height_ratio = min_body_height_ratio
        self.min_body_width_ratio = min_body_width_ratio
        self.min_upper_body_height_ratio = min_upper_body_height_ratio
        self.min_upper_body_width_ratio = min_upper_body_width_ratio
        self.min_visible_pose_points = min_visible_pose_points

        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            enable_segmentation=False,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.last_result = self._empty_result()

    def _empty_result(self):
        return {
            "human_detected": False,
            "bbox": None,
            "face_bbox": None,
            "points": {},
            "connections": [],
            "body_center": None,
            "body_center_norm": None,
            "torso_center": None,
            "torso_center_norm": None,
            "upper_body_center": None,
            "upper_body_center_norm": None,
            "shoulder_center": None,
            "shoulder_center_norm": None,
            "eyes_center": None,
            "eyes_center_norm": None,
            "nose_center": None,
            "nose_center_norm": None,
            "ears_center": None,
            "ears_center_norm": None,
            "face_center": None,
            "face_center_norm": None,
            "method": "none",
        }

    @staticmethod
    def _to_norm(point, frame_width, frame_height):
        if point is None:
            return None
        return point[0] / frame_width, point[1] / frame_height

    @staticmethod
    def _average_points(points):
        valid = [point for point in points if point is not None]
        if not valid:
            return None
        x = int(sum(point[0] for point in valid) / len(valid))
        y = int(sum(point[1] for point in valid) / len(valid))
        return x, y

    def _get_point(self, landmarks, landmark_id, frame_width, frame_height):
        landmark = landmarks[landmark_id]
        if landmark.visibility < self.landmark_visibility:
            return None

        x = int(landmark.x * frame_width)
        y = int(landmark.y * frame_height)
        if not (0 <= x < frame_width and 0 <= y < frame_height):
            return None
        return x, y

    @staticmethod
    def _make_bbox_from_points(points, frame_width, frame_height, margin=40):
        valid = [point for point in points if point is not None]
        if not valid:
            return None

        xs = [point[0] for point in valid]
        ys = [point[1] for point in valid]
        return (
            max(min(xs) - margin, 0),
            max(min(ys) - margin, 0),
            min(max(xs) + margin, frame_width - 1),
            min(max(ys) + margin, frame_height - 1),
        )

    @staticmethod
    def _bbox_center(bbox):
        if bbox is None:
            return None
        x1, y1, x2, y2 = bbox
        return int((x1 + x2) / 2), int((y1 + y2) / 2)

    @staticmethod
    def _bbox_size_ratios(bbox, frame_width, frame_height):
        x1, y1, x2, y2 = bbox
        return (x2 - x1) / frame_width, (y2 - y1) / frame_height

    def _detect_face_fallback(self, frame):
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(50, 50),
        )

        if len(faces) == 0:
            return self._empty_result()

        x, y, face_width, face_height = max(
            faces, key=lambda box: box[2] * box[3]
        )
        face_bbox = (x, y, x + face_width, y + face_height)
        face_center = (x + face_width // 2, y + face_height // 2)
        face_center_norm = self._to_norm(face_center, width, height)

        result = self._empty_result()
        result.update(
            {
                "human_detected": True,
                "bbox": face_bbox,
                "face_bbox": face_bbox,
                "body_center": face_center,
                "body_center_norm": face_center_norm,
                "face_center": face_center,
                "face_center_norm": face_center_norm,
                "method": "opencv_face_fallback",
            }
        )
        return result

    def _full_torso_center(self, points):
        required = [
            "left_shoulder",
            "right_shoulder",
            "left_hip",
            "right_hip",
        ]
        if any(key not in points for key in required):
            return None
        return self._average_points([points[key] for key in required])

    def _upper_body_center(self, points):
        keys = [
            "left_shoulder",
            "right_shoulder",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist",
        ]
        available = [points[key] for key in keys if key in points]
        if len(available) < 2:
            return None
        return self._average_points(available)

    def _has_valid_upper_body(self, points, frame_width, frame_height):
        keys = [
            "left_shoulder",
            "right_shoulder",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist",
        ]
        available = [points[key] for key in keys if key in points]
        if len(available) < 2:
            return False

        bbox = self._make_bbox_from_points(
            available, frame_width, frame_height, margin=30
        )
        if bbox is None:
            return False

        width_ratio, height_ratio = self._bbox_size_ratios(
            bbox, frame_width, frame_height
        )
        size_ok = (
            width_ratio >= self.min_upper_body_width_ratio
            and height_ratio >= self.min_upper_body_height_ratio
        )
        shoulder_ok = (
            "left_shoulder" in points or "right_shoulder" in points
        )
        return size_ok and shoulder_ok

    def update(self, frame):
        frame_height, frame_width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        pose_result = self.pose.process(rgb)

        if not pose_result.pose_landmarks:
            self.last_result = (
                self._detect_face_fallback(frame)
                if self.enable_face_fallback
                else self._empty_result()
            )
            return self.last_result

        landmarks = pose_result.pose_landmarks.landmark
        pose_ids = self.mp_pose.PoseLandmark
        keypoint_map = {
            "nose": pose_ids.NOSE.value,
            "left_eye": pose_ids.LEFT_EYE.value,
            "right_eye": pose_ids.RIGHT_EYE.value,
            "left_ear": pose_ids.LEFT_EAR.value,
            "right_ear": pose_ids.RIGHT_EAR.value,
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
            "left_ankle": pose_ids.LEFT_ANKLE.value,
            "right_ankle": pose_ids.RIGHT_ANKLE.value,
        }

        points = {}
        for name, landmark_id in keypoint_map.items():
            point = self._get_point(
                landmarks, landmark_id, frame_width, frame_height
            )
            if point is not None:
                points[name] = point

        visible_pose_points = []
        for landmark in landmarks:
            if landmark.visibility < self.landmark_visibility:
                continue
            x = int(landmark.x * frame_width)
            y = int(landmark.y * frame_height)
            if 0 <= x < frame_width and 0 <= y < frame_height:
                visible_pose_points.append((x, y))

        if len(visible_pose_points) < self.min_visible_pose_points:
            self.last_result = (
                self._detect_face_fallback(frame)
                if self.enable_face_fallback
                else self._empty_result()
            )
            return self.last_result

        body_bbox = self._make_bbox_from_points(
            visible_pose_points, frame_width, frame_height, margin=40
        )
        if body_bbox is None:
            self.last_result = self._empty_result()
            return self.last_result

        body_width_ratio, body_height_ratio = self._bbox_size_ratios(
            body_bbox, frame_width, frame_height
        )
        body_size_ok = (
            body_width_ratio >= self.min_body_width_ratio
            and body_height_ratio >= self.min_body_height_ratio
        )
        upper_body_valid = self._has_valid_upper_body(
            points, frame_width, frame_height
        )

        torso_center = self._full_torso_center(points)
        if self.strict_torso_validation and torso_center is None:
            body_size_ok = False

        if not body_size_ok and not upper_body_valid:
            self.last_result = (
                self._detect_face_fallback(frame)
                if self.enable_face_fallback
                else self._empty_result()
            )
            return self.last_result

        eyes_center = None
        if "left_eye" in points and "right_eye" in points:
            eyes_center = self._average_points(
                [points["left_eye"], points["right_eye"]]
            )

        ears_center = None
        if "left_ear" in points and "right_ear" in points:
            ears_center = self._average_points(
                [points["left_ear"], points["right_ear"]]
            )

        shoulder_center = None
        if "left_shoulder" in points and "right_shoulder" in points:
            shoulder_center = self._average_points(
                [points["left_shoulder"], points["right_shoulder"]]
            )

        nose_center = points.get("nose")
        head_points = [
            points.get("left_eye"),
            points.get("right_eye"),
            points.get("left_ear"),
            points.get("right_ear"),
            nose_center,
        ]
        face_center = self._average_points(head_points)
        face_bbox = self._make_bbox_from_points(
            head_points, frame_width, frame_height, margin=25
        )

        upper_body_center = self._upper_body_center(points)
        body_center = self._bbox_center(body_bbox)

        connections = [
            ("left_eye", "right_eye"),
            ("left_ear", "left_eye"),
            ("right_ear", "right_eye"),
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
            ("left_knee", "left_ankle"),
            ("right_knee", "right_ankle"),
        ]

        if face_center is not None:
            method = "mediapipe_head"
        elif torso_center is not None:
            method = "mediapipe_full_torso"
        elif upper_body_center is not None:
            method = "mediapipe_upper_body"
        else:
            method = "mediapipe_body_bbox"

        self.last_result = {
            "human_detected": True,
            "bbox": body_bbox,
            "face_bbox": face_bbox,
            "points": points,
            "connections": connections,
            "body_center": body_center,
            "body_center_norm": self._to_norm(
                body_center, frame_width, frame_height
            ),
            "torso_center": torso_center,
            "torso_center_norm": self._to_norm(
                torso_center, frame_width, frame_height
            ),
            "upper_body_center": upper_body_center,
            "upper_body_center_norm": self._to_norm(
                upper_body_center, frame_width, frame_height
            ),
            "shoulder_center": shoulder_center,
            "shoulder_center_norm": self._to_norm(
                shoulder_center, frame_width, frame_height
            ),
            "eyes_center": eyes_center,
            "eyes_center_norm": self._to_norm(
                eyes_center, frame_width, frame_height
            ),
            "nose_center": nose_center,
            "nose_center_norm": self._to_norm(
                nose_center, frame_width, frame_height
            ),
            "ears_center": ears_center,
            "ears_center_norm": self._to_norm(
                ears_center, frame_width, frame_height
            ),
            "face_center": face_center,
            "face_center_norm": self._to_norm(
                face_center, frame_width, frame_height
            ),
            "method": method,
        }
        return self.last_result

    def close(self):
        self.pose.close()
