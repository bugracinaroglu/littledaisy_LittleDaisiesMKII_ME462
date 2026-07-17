import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from collections import deque
import math
import os


class GestureDetector:
    def __init__(
        self,
        process_every_n_frames=1,
        max_num_hands=2,
        detection_confidence=0.60,
        tracking_confidence=0.60,
        wave_history_size=20,
        wave_min_x_range=0.08,
        wave_min_direction_changes=1,
        wave_min_step=0.008,
        open_palm_enabled=True,
        open_palm_min_fingers=5,
        open_palm_hold_frames=4,
        hello_cooldown_frames=30
    ):
        self.process_every_n_frames = process_every_n_frames
        self.max_num_hands = max_num_hands

        self.wave_min_x_range = wave_min_x_range
        self.wave_min_direction_changes = wave_min_direction_changes
        self.wave_min_step = wave_min_step

        self.open_palm_enabled = open_palm_enabled
        self.open_palm_min_fingers = open_palm_min_fingers
        self.open_palm_hold_frames = open_palm_hold_frames

        self.hello_cooldown_frames = hello_cooldown_frames

        self.frame_count = 0
        self.last_hello_frame = -9999

        self.x_histories = [
            deque(maxlen=wave_history_size)
            for _ in range(max_num_hands)
        ]

        self.open_palm_counts = [0 for _ in range(max_num_hands)]

        self.open_palm_counts = [0 for _ in range(max_num_hands)]

        model_path = os.path.join(
            os.path.dirname(__file__), 
            'models', 
            'gesture_recognizer.task'
        )

        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.GestureRecognizerOptions(
            base_options=base_options,
            num_hands=max_num_hands,
            min_hand_detection_confidence=detection_confidence,
            min_hand_presence_confidence=tracking_confidence,
            min_tracking_confidence=tracking_confidence
        )
        self.recognizer = vision.GestureRecognizer.create_from_options(options)

        self.last_result = self._empty_result()

    def _empty_result(self):
        return {
            "hand_detected": False,
            "hands": [],
            "waving": False,
            "open_palm": False,
            "hello_event": False
        }

    def _distance(self, a, b):
        return math.sqrt(
            (a.x - b.x) ** 2 +
            (a.y - b.y) ** 2
        )

    def _get_hand_center(self, landmarks):
        ids = [0, 5, 9, 13, 17]

        cx = sum(landmarks[i].x for i in ids) / len(ids)
        cy = sum(landmarks[i].y for i in ids) / len(ids)

        return cx, cy

    def _count_extended_fingers(self, landmarks):
        # We no longer calculate this manually. The GestureRecognizer does it.
        return 0, {}

    def _count_direction_changes(self, xs):
        directions = []

        for i in range(1, len(xs)):
            dx = xs[i] - xs[i - 1]

            if abs(dx) < self.wave_min_step:
                continue

            directions.append(1 if dx > 0 else -1)

        if len(directions) < 2:
            return 0

        changes = 0

        for i in range(1, len(directions)):
            if directions[i] != directions[i - 1]:
                changes += 1

        return changes

    def _detect_wave(self, hand_index):
        history = self.x_histories[hand_index]

        if len(history) < 6:
            return False, 0.0, 0

        xs = list(history)

        x_range = max(xs) - min(xs)
        direction_changes = self._count_direction_changes(xs)

        waving = (
            x_range >= self.wave_min_x_range
            and direction_changes >= self.wave_min_direction_changes
        )

        return waving, x_range, direction_changes

    def update(self, frame):
        self.frame_count += 1

        if self.frame_count % self.process_every_n_frames != 0:
            return self.last_result

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = self.recognizer.recognize(mp_image)

        if not result.hand_landmarks:
            for history in self.x_histories:
                history.clear()

            self.open_palm_counts = [0 for _ in range(self.max_num_hands)]

            self.last_result = self._empty_result()
            return self.last_result

        detected_hands = []
        any_waving = False
        any_open_palm = False
        any_hello_event = False

        for hand_index, hand_landmarks in enumerate(result.hand_landmarks):
            if hand_index >= self.max_num_hands:
                break
            
            # The recognizer returns a list of NormalizedLandmarks, but we want 
            # to pass an object with `.landmark` so the old visualizer code is happy.
            class DummyLandmarkList:
                def __init__(self, lms):
                    self.landmark = lms
            
            hand_landmarks_obj = DummyLandmarkList(hand_landmarks)

            center = self._get_hand_center(hand_landmarks)

            self.x_histories[hand_index].append(center[0])

            waving, x_range, direction_changes = self._detect_wave(hand_index)
            
            open_palm_now = False
            if self.open_palm_enabled and len(result.gestures) > hand_index:
                gestures = result.gestures[hand_index]
                if any(g.category_name == "Open_Palm" for g in gestures):
                    open_palm_now = True

            if open_palm_now:
                self.open_palm_counts[hand_index] += 1
            else:
                self.open_palm_counts[hand_index] = 0

            open_palm_confirmed = (
                self.open_palm_counts[hand_index] >= self.open_palm_hold_frames
            )

            hello_event = False
            hello_reason = None

            if waving:
                hello_reason = "wave"

            if open_palm_confirmed:
                hello_reason = "open_palm"

            if hello_reason is not None:
                frames_since_last_hello = self.frame_count - self.last_hello_frame

                if frames_since_last_hello >= self.hello_cooldown_frames:
                    hello_event = True
                    self.last_hello_frame = self.frame_count
                    print(
                        f"[Gesture] Hello detected from hand {hand_index + 1}, reason: {hello_reason}"
                    )

            any_waving = any_waving or waving
            any_open_palm = any_open_palm or open_palm_confirmed
            any_hello_event = any_hello_event or hello_event

            detected_hands.append({
                "hand_index": hand_index,
                "landmarks": hand_landmarks_obj,
                "center_norm": center,
                "waving": waving,
                "open_palm": open_palm_confirmed,
                "hello_event": hello_event,
                "hello_reason": hello_reason,
                "finger_count": 5 if open_palm_confirmed else 0,
                "finger_states": {},
                "x_range": x_range,
                "direction_changes": direction_changes
            })

        self.last_result = {
            "hand_detected": True,
            "hands": detected_hands,
            "waving": any_waving,
            "open_palm": any_open_palm,
            "hello_event": any_hello_event
        }

        return self.last_result

    def close(self):
        self.recognizer.close()