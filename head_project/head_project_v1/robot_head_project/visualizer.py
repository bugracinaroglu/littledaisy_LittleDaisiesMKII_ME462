import cv2


class Visualizer:
    def __init__(self):
        self.hand_connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
            (5, 9), (9, 13), (13, 17)
        ]

    def draw_text_box(
        self,
        frame,
        text,
        pos,
        bg=(40, 40, 40),
        color=(255, 255, 255),
        scale=0.65,
        thickness=2
    ):
        x, y = pos
        font = cv2.FONT_HERSHEY_SIMPLEX

        (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)

        cv2.rectangle(
            frame,
            (x - 5, y - th - 8),
            (x + tw + 5, y + baseline + 5),
            bg,
            -1
        )

        cv2.putText(
            frame,
            text,
            (x, y),
            font,
            scale,
            color,
            thickness,
            cv2.LINE_AA
        )

    def draw_human(self, frame, human_result):
        if human_result is None:
            return frame

        if not human_result.get("human_detected", False):
            self.draw_text_box(
                frame,
                "Human: Not detected",
                (30, 330),
                bg=(0, 0, 150)
            )
            return frame

        bbox = human_result.get("bbox", None)
        points = human_result.get("points", {})
        connections = human_result.get("connections", [])
        body_center = human_result.get("body_center", None)
        torso_center = human_result.get("torso_center", None)

        if bbox is not None:
            x1, y1, x2, y2 = bbox

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (255, 255, 0),
                2
            )

        for p1_name, p2_name in connections:
            if p1_name in points and p2_name in points:
                cv2.line(
                    frame,
                    points[p1_name],
                    points[p2_name],
                    (255, 255, 0),
                    2
                )

        for point in points.values():
            cv2.circle(
                frame,
                point,
                6,
                (0, 0, 255),
                -1
            )

        if body_center is not None:
            cv2.circle(frame, body_center, 9, (0, 255, 255), -1)
            cv2.putText(
                frame,
                "body center",
                (body_center[0] + 10, body_center[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 255),
                2,
                cv2.LINE_AA
            )

        if torso_center is not None:
            cv2.circle(frame, torso_center, 8, (0, 165, 255), -1)
            cv2.putText(
                frame,
                "torso center",
                (torso_center[0] + 10, torso_center[1] + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 165, 255),
                2,
                cv2.LINE_AA
            )

        self.draw_text_box(
            frame,
            "Human: detected",
            (30, 330),
            bg=(60, 90, 0)
        )

        return frame

    def draw_emotion(self, frame, emotion_result):
        if emotion_result is None:
            return frame

        dominant = emotion_result.get("dominant", "No face")
        scores = emotion_result.get("top_scores", [])
        region = emotion_result.get("region", None)

        if region is not None:
            x = int(region.get("x", 0))
            y = int(region.get("y", 0))
            w = int(region.get("w", 0))
            h = int(region.get("h", 0))

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

        self.draw_text_box(
            frame,
            f"Emotion: {dominant}",
            (30, 50),
            bg=(30, 80, 30),
            scale=0.8
        )

        y0 = 90

        for i, (emotion, score) in enumerate(scores):
            cv2.putText(
                frame,
                f"{emotion}: {score:.1f}%",
                (30, y0 + i * 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 255, 255),
                2,
                cv2.LINE_AA
            )

        return frame

    def draw_gesture(self, frame, gesture_result):
        if gesture_result is None:
            return frame

        hand_detected = gesture_result.get("hand_detected", False)
        hands = gesture_result.get("hands", [])
        any_waving = gesture_result.get("waving", False)
        any_hello_event = gesture_result.get("hello_event", False)

        h, w = frame.shape[:2]

        if not hand_detected:
            self.draw_text_box(
                frame,
                "Gesture: No hand",
                (30, 440),
                bg=(90, 0, 90)
            )
            return frame

        for hand in hands:
            hand_index = hand.get("hand_index", 0)
            landmarks = hand.get("landmarks", None)
            center = hand.get("center_norm", None)
            waving = hand.get("waving", False)
            x_range = hand.get("x_range", 0.0)
            direction_changes = hand.get("direction_changes", 0)

            if landmarks is not None:
                lm_list = landmarks.landmark

                for a, b in self.hand_connections:
                    x1 = int(lm_list[a].x * w)
                    y1 = int(lm_list[a].y * h)
                    x2 = int(lm_list[b].x * w)
                    y2 = int(lm_list[b].y * h)

                    cv2.line(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (255, 0, 255),
                        2
                    )

                for lm in lm_list:
                    x = int(lm.x * w)
                    y = int(lm.y * h)
                    cv2.circle(frame, (x, y), 4, (255, 0, 255), -1)

            if center is not None:
                cx = int(center[0] * w)
                cy = int(center[1] * h)

                cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)

                cv2.putText(
                    frame,
                    f"hand {hand_index + 1}",
                    (cx + 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 0, 255),
                    2,
                    cv2.LINE_AA
                )

            status = "WAVE" if waving else "detected"
            y_text = 440 + hand_index * 55

            self.draw_text_box(
                frame,
                f"Hand {hand_index + 1}: {status}",
                (30, y_text),
                bg=(90, 0, 90),
                scale=0.65
            )

            cv2.putText(
                frame,
                f"x_range={x_range:.2f}, dir={direction_changes}",
                (30, y_text + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 0, 255),
                2,
                cv2.LINE_AA
            )

        if any_waving:
            self.draw_text_box(
                frame,
                "Gesture: HELLO / WAVE",
                (30, 560),
                bg=(120, 0, 120),
                scale=0.75
            )

        if any_hello_event:
            cv2.putText(
                frame,
                "HELLO DETECTED!",
                (30, 610),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 0, 255),
                3,
                cv2.LINE_AA
            )

        return frame

    def draw_target(self, frame, target):
        if target is None or not target.get("valid", False):
            self.draw_text_box(
                frame,
                "Target: none",
                (30, 250),
                bg=(0, 0, 150)
            )
            return frame

        h, w = frame.shape[:2]

        center_norm = target.get("center_norm", None)
        target_type = target.get("target_type", "unknown")
        error_norm = target.get("error_norm", None)

        if center_norm is not None:
            cx = int(center_norm[0] * w)
            cy = int(center_norm[1] * h)

            cv2.circle(frame, (cx, cy), 12, (0, 255, 255), 2)
            cv2.line(frame, (w // 2, cy), (cx, cy), (0, 255, 255), 2)

        if error_norm is not None:
            ex, ey = error_norm
            text = f"Target: {target_type}, error=({ex:.2f}, {ey:.2f})"
        else:
            text = f"Target: {target_type}"

        self.draw_text_box(
            frame,
            text,
            (30, 250),
            bg=(70, 70, 0)
        )

        return frame

    def draw_control(self, frame, mapping_result, serial_connected):
        if mapping_result is None:
            return frame

        angle = mapping_result.get("target_angle", 0.0)
        raw_angle = mapping_result.get("raw_angle", 0.0)
        angle_error = mapping_result.get("angle_error_deg", 0.0)
        filtered = mapping_result.get("filtered_angle_error_deg", 0.0)
        decision = mapping_result.get("decision", "none")

        self.draw_text_box(
            frame,
            f"Decision: {decision}",
            (30, 285),
            bg=(50, 50, 50)
        )

        self.draw_text_box(
            frame,
            f"Head angle: {angle:.1f} deg | raw: {raw_angle:.1f}",
            (30, 690),
            bg=(50, 50, 50),
            scale=0.60
        )

        self.draw_text_box(
            frame,
            f"Angle error: {angle_error:.2f} deg | filtered: {filtered:.2f}",
            (420, 690),
            bg=(50, 50, 50),
            scale=0.60
        )

        serial_text = "Serial: ON" if serial_connected else "Serial: OFF"

        self.draw_text_box(
            frame,
            serial_text,
            (950, 690),
            bg=(50, 50, 50),
            scale=0.60
        )

        return frame

    def draw_fps(self, frame, fps):
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (frame.shape[1] - 150, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA
        )

        return frame