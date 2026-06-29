import cv2
import mediapipe as mp
from collections import deque
import math


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

        self.mp_hands = mp.solutions.hands

        self.hands_detector = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            model_complexity=0,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence
        )

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
        """
        Orientation-friendly finger extension check.
        It checks whether fingertip is farther from palm center than the lower joint.
        """

        palm_ids = [0, 5, 9, 13, 17]

        class Dummy:
            pass

        palm = Dummy()
        palm.x = sum(landmarks[i].x for i in palm_ids) / len(palm_ids)
        palm.y = sum(landmarks[i].y for i in palm_ids) / len(palm_ids)

        finger_defs = {
            "thumb": (4, 3),
            "index": (8, 6),
            "middle": (12, 10),
            "ring": (16, 14),
            "pinky": (20, 18),
        }

        states = {}
        count = 0

        for name, (tip_id, lower_id) in finger_defs.items():
            tip_dist = self._distance(landmarks[tip_id], palm)
            lower_dist = self._distance(landmarks[lower_id], palm)

            extended = tip_dist > lower_dist * 1.12

            states[name] = extended

            if extended:
                count += 1

        return count, states

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
        rgb.flags.writeable = False

        result = self.hands_detector.process(rgb)

        if not result.multi_hand_landmarks:
            for history in self.x_histories:
                history.clear()

            self.open_palm_counts = [0 for _ in range(self.max_num_hands)]

            self.last_result = self._empty_result()
            return self.last_result

        detected_hands = []
        any_waving = False
        any_open_palm = False
        any_hello_event = False

        for hand_index, hand_landmarks in enumerate(result.multi_hand_landmarks):
            if hand_index >= self.max_num_hands:
                break

            landmarks = hand_landmarks.landmark
            center = self._get_hand_center(landmarks)

            self.x_histories[hand_index].append(center[0])

            waving, x_range, direction_changes = self._detect_wave(hand_index)

            finger_count, finger_states = self._count_extended_fingers(landmarks)

            open_palm_now = (
                self.open_palm_enabled and
                finger_count >= self.open_palm_min_fingers
            )

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
                "landmarks": hand_landmarks,
                "center_norm": center,
                "waving": waving,
                "open_palm": open_palm_confirmed,
                "hello_event": hello_event,
                "hello_reason": hello_reason,
                "finger_count": finger_count,
                "finger_states": finger_states,
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
        self.hands_detector.close()