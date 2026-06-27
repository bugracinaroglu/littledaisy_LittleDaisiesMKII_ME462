import cv2
import mediapipe as mp


class HumanTracker:
    def __init__(
        self,
        detection_confidence=0.70,
        tracking_confidence=0.70,
        strict_torso_validation=False,
        enable_face_fallback=True,
        min_body_height_ratio=0.16,
        min_body_width_ratio=0.08,
        min_upper_body_height_ratio=0.10,
        min_upper_body_width_ratio=0.08,
        min_visible_pose_points=5
    ):
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
            min_tracking_confidence=tracking_confidence
        )

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
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

            "upper_body_center": None,
            "upper_body_center_norm": None,

            "face_center_norm": None,

            "method": "none"
        }

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

    def _get_point(self, landmarks, landmark_id, frame_width, frame_height):
        lm = landmarks[landmark_id]

        if lm.visibility < 0.45:
            return None

        x = int(lm.x * frame_width)
        y = int(lm.y * frame_height)

        if x < 0 or x >= frame_width or y < 0 or y >= frame_height:
            return None

        return x, y

    def _make_bbox_from_points(self, points, frame_width, frame_height, margin=40):
        if len(points) == 0:
            return None

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        x1 = max(min(xs) - margin, 0)
        y1 = max(min(ys) - margin, 0)
        x2 = min(max(xs) + margin, frame_width - 1)
        y2 = min(max(ys) + margin, frame_height - 1)

        return x1, y1, x2, y2

    def _bbox_center(self, bbox):
        x1, y1, x2, y2 = bbox

        return (
            int((x1 + x2) / 2),
            int((y1 + y2) / 2)
        )

    def _bbox_size_ratios(self, bbox, frame_width, frame_height):
        x1, y1, x2, y2 = bbox

        width_ratio = (x2 - x1) / frame_width
        height_ratio = (y2 - y1) / frame_height

        return width_ratio, height_ratio

    def _detect_face_fallback(self, frame):
        h, w = frame.shape[:2]

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=6,
            minSize=(50, 50)
        )

        if len(faces) == 0:
            return self._empty_result()

        faces = sorted(
            faces,
            key=lambda box: box[2] * box[3],
            reverse=True
        )

        x, y, fw, fh = faces[0]

        cx = x + fw // 2
        cy = y + fh // 2

        bbox = (x, y, x + fw, y + fh)
        face_center = (cx, cy)
        face_center_norm = self._to_norm(face_center, w, h)

        return {
            "human_detected": True,
            "bbox": bbox,
            "points": {},
            "connections": [],

            "body_center": face_center,
            "body_center_norm": face_center_norm,

            "torso_center": None,
            "torso_center_norm": None,

            "upper_body_center": None,
            "upper_body_center_norm": None,

            "face_center_norm": face_center_norm,

            "method": "opencv_face_fallback"
        }

    def _full_torso_center(self, points):
        required = [
            "left_shoulder",
            "right_shoulder",
            "left_hip",
            "right_hip"
        ]

        for key in required:
            if key not in points:
                return None

        return self._average_points([
            points.get("left_shoulder"),
            points.get("right_shoulder"),
            points.get("left_hip"),
            points.get("right_hip")
        ])

    def _upper_body_center(self, points):
        """
        Used when hips are not visible.
        This is better than face-only tracking for close camera views.
        """

        useful_keys = [
            "left_shoulder",
            "right_shoulder",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist"
        ]

        useful_points = []

        for key in useful_keys:
            if key in points:
                useful_points.append(points[key])

        if len(useful_points) < 2:
            return None

        return self._average_points(useful_points)

    def _has_valid_upper_body(self, points, frame_width, frame_height):
        upper_keys = [
            "left_shoulder",
            "right_shoulder",
            "left_elbow",
            "right_elbow",
            "left_wrist",
            "right_wrist"
        ]

        upper_points = []

        for key in upper_keys:
            if key in points:
                upper_points.append(points[key])

        if len(upper_points) < 2:
            return False

        bbox = self._make_bbox_from_points(
            upper_points,
            frame_width,
            frame_height,
            margin=30
        )

        if bbox is None:
            return False

        width_ratio, height_ratio = self._bbox_size_ratios(
            bbox,
            frame_width,
            frame_height
        )

        size_ok = (
            width_ratio >= self.min_upper_body_width_ratio and
            height_ratio >= self.min_upper_body_height_ratio
        )

        # At least one shoulder is very useful.
        shoulder_ok = (
            "left_shoulder" in points or
            "right_shoulder" in points
        )

        return size_ok and shoulder_ok

    def update(self, frame):
        h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False

        result = self.pose.process(rgb)

        if not result.pose_landmarks:
            if self.enable_face_fallback:
                self.last_result = self._detect_face_fallback(frame)
                return self.last_result

            self.last_result = self._empty_result()
            return self.last_result

        landmarks = result.pose_landmarks.landmark
        pose_ids = self.mp_pose.PoseLandmark

        keypoint_map = {
            "nose": pose_ids.NOSE.value,

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

        visible_pose_points = []

        for lm in landmarks:
            if lm.visibility > 0.45:
                x = int(lm.x * w)
                y = int(lm.y * h)

                if 0 <= x < w and 0 <= y < h:
                    visible_pose_points.append((x, y))

        if len(visible_pose_points) < self.min_visible_pose_points:
            if self.enable_face_fallback:
                self.last_result = self._detect_face_fallback(frame)
                return self.last_result

            self.last_result = self._empty_result()
            return self.last_result

        body_bbox = self._make_bbox_from_points(
            visible_pose_points,
            w,
            h,
            margin=40
        )

        if body_bbox is None:
            self.last_result = self._empty_result()
            return self.last_result

        body_width_ratio, body_height_ratio = self._bbox_size_ratios(
            body_bbox,
            w,
            h
        )

        body_size_ok = (
            body_width_ratio >= self.min_body_width_ratio and
            body_height_ratio >= self.min_body_height_ratio
        )

        upper_body_valid = self._has_valid_upper_body(points, w, h)

        if not body_size_ok and not upper_body_valid:
            if self.enable_face_fallback:
                self.last_result = self._detect_face_fallback(frame)
                return self.last_result

            self.last_result = self._empty_result()
            return self.last_result

        torso_center = self._full_torso_center(points)

        if torso_center is not None:
            torso_center_norm = self._to_norm(torso_center, w, h)
        else:
            torso_center_norm = None

        upper_body_center = self._upper_body_center(points)

        if upper_body_center is not None:
            upper_body_center_norm = self._to_norm(upper_body_center, w, h)
        else:
            upper_body_center_norm = None

        body_center = self._bbox_center(body_bbox)
        body_center_norm = self._to_norm(body_center, w, h)

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

        if torso_center is not None:
            method = "mediapipe_full_torso"
        elif upper_body_center is not None:
            method = "mediapipe_upper_body"
        else:
            method = "mediapipe_body_bbox"

        self.last_result = {
            "human_detected": True,
            "bbox": body_bbox,
            "points": points,
            "connections": connections,

            "body_center": body_center,
            "body_center_norm": body_center_norm,

            "torso_center": torso_center,
            "torso_center_norm": torso_center_norm,

            "upper_body_center": upper_body_center,
            "upper_body_center_norm": upper_body_center_norm,

            "face_center_norm": None,

            "method": method
        }

        return self.last_result

    def close(self):
        self.pose.close()