import cv2
import numpy as np


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
        any_open_palm = gesture_result.get("open_palm", False)
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
            open_palm = hand.get("open_palm", False)
            finger_count = hand.get("finger_count", 0)
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

            if open_palm:
                status = "OPEN PALM"
            elif waving:
                status = "WAVE"
            else:
                status = "detected"

            y_text = 440 + hand_index * 60

            self.draw_text_box(
                frame,
                f"Hand {hand_index + 1}: {status}",
                (30, y_text),
                bg=(90, 0, 90),
                scale=0.65
            )

            cv2.putText(
                frame,
                f"fingers={finger_count}, x_range={x_range:.2f}, dir={direction_changes}",
                (30, y_text + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 0, 255),
                2,
                cv2.LINE_AA
            )

        if any_waving or any_open_palm:
            self.draw_text_box(
                frame,
                "Gesture: HELLO",
                (30, 570),
                bg=(120, 0, 120),
                scale=0.75
            )

        if any_hello_event:
            cv2.putText(
                frame,
                "HELLO DETECTED!",
                (30, 620),
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
        center_norm = target.get("center_norm")
        target_type = target.get("target_type", "unknown")
        distance_m = target.get("distance_m")
        distance_source = target.get("distance_source", "unknown")

        if center_norm is not None:
            cx = int(center_norm[0] * w)
            cy = int(center_norm[1] * h)
            cv2.circle(frame, (cx, cy), 12, (0, 255, 255), 2)
            cv2.line(frame, (w // 2, h // 2), (cx, cy), (0, 255, 255), 2)

        if distance_m is None:
            distance_text = "distance=direction only"
        else:
            distance_text = f"distance={distance_m:.2f} m ({distance_source})"

        self.draw_text_box(
            frame,
            f"Target: {target_type} | {distance_text}",
            (30, 250),
            bg=(70, 70, 0),
            scale=0.60
        )
        return frame

    def draw_control(self, frame, mapping_result, serial_connected):
        if mapping_result is None:
            return frame

        pan = mapping_result.get("pan_angle", 0.0)
        tilt = mapping_result.get("tilt_angle", 0.0)
        raw_pan = mapping_result.get("raw_pan_angle", 0.0)
        raw_tilt = mapping_result.get("raw_tilt_angle", 0.0)
        pan_error = mapping_result.get("pan_error_deg", 0.0)
        tilt_error = mapping_result.get("tilt_error_deg", 0.0)
        decision = mapping_result.get("decision", "none")
        metric = mapping_result.get("metric_offset_compensation", False)
        tilt_enabled = mapping_result.get("tilt_tracking_enabled", False)

        self.draw_text_box(
            frame,
            f"Decision: {decision}",
            (30, 285),
            bg=(50, 50, 50),
            scale=0.60
        )

        self.draw_text_box(
            frame,
            f"Pan: {pan:.1f} deg (raw {raw_pan:.1f}) | Tilt: {tilt:.1f} deg (raw {raw_tilt:.1f})",
            (30, 690),
            bg=(50, 50, 50),
            scale=0.55
        )

        self.draw_text_box(
            frame,
            f"Camera angles: pan {pan_error:.2f} deg | tilt {tilt_error:.2f} deg",
            (500, 690),
            bg=(50, 50, 50),
            scale=0.55
        )

        serial_text = "Serial: ON" if serial_connected else "Serial: OFF"
        compensation_text = "20 cm correction: ON" if metric else "20 cm correction: OFF"
        tilt_text = "Tilt tracking: ON" if tilt_enabled else "Tilt tracking: OFF"

        self.draw_text_box(
            frame,
            f"{serial_text} | {compensation_text} | {tilt_text}",
            (30, 650),
            bg=(50, 50, 50),
            scale=0.55
        )
        return frame

    @staticmethod
    def _status_bool(value):
        return "ON" if bool(value) else "OFF"

    @staticmethod
    def _safe_number(value, digits=1, suffix=""):
        if value is None:
            return "--"
        try:
            return f"{float(value):.{digits}f}{suffix}"
        except (TypeError, ValueError):
            return "--"

    def compose_status_panel(self, frame, status, panel_width=360):
        """Append a compact live-status panel to the right of the camera frame."""
        panel_width = max(int(panel_width), 280)
        height = frame.shape[0]
        panel = np.zeros((height, panel_width, 3), dtype=np.uint8)
        panel[:] = (24, 27, 31)

        # A thin separator makes the panel visually independent from the image.
        cv2.line(panel, (0, 0), (0, height - 1), (95, 105, 115), 2)

        font = cv2.FONT_HERSHEY_SIMPLEX
        x_label = 18
        x_value = panel_width - 18
        y = 36

        def title(text):
            nonlocal y
            cv2.putText(
                panel, text, (x_label, y), font, 0.76,
                (245, 245, 245), 2, cv2.LINE_AA
            )
            y += 18
            cv2.line(
                panel, (x_label, y), (panel_width - 18, y),
                (70, 77, 84), 1
            )
            y += 24

        def section(text):
            nonlocal y
            y += 7
            cv2.putText(
                panel, text.upper(), (x_label, y), font, 0.49,
                (170, 185, 200), 1, cv2.LINE_AA
            )
            y += 20

        def row(label, value, value_color=(235, 235, 235)):
            nonlocal y
            value = str(value)
            cv2.putText(
                panel, str(label), (x_label, y), font, 0.49,
                (175, 180, 185), 1, cv2.LINE_AA
            )
            (tw, _), _ = cv2.getTextSize(value, font, 0.49, 1)
            cv2.putText(
                panel, value, (max(x_label + 120, x_value - tw), y),
                font, 0.49, value_color, 1, cv2.LINE_AA
            )
            y += 22

        def state_row(label, enabled):
            color = (90, 220, 120) if enabled else (110, 120, 130)
            row(label, self._status_bool(enabled), color)

        title("ROBOT HEAD STATUS")

        section("Control authority")
        control_mode = status.get("control_mode", "--")
        mode_colors = {
            "AUTO": (90, 220, 120),
            "MANUAL": (80, 190, 245),
            "ROS": (220, 160, 90),
        }
        row("Active mode", control_mode, mode_colors.get(control_mode, (235, 235, 235)))
        state_row("Auto commands", status.get("auto_commands_active", False))
        row("Last source", status.get("last_source", "--"))
        row("Last command", status.get("last_command", "--"))

        features = status.get("features", {})
        section("Active features")
        state_row("Head tracking", features.get("head_tracking", False))
        state_row("Tilt tracking", features.get("tilt_tracking", False))
        state_row("Emotion", features.get("emotion", False))
        state_row("Gesture", features.get("gesture", False))
        state_row("LCD face", features.get("lcd_face", False))
        state_row("Arm wave", features.get("arm_wave", False))

        section("Detection")
        state_row("Human", status.get("human_detected", False))
        state_row("Target", status.get("target_valid", False))
        state_row("Hand", status.get("hand_detected", False))
        serial_connected = status.get("serial_connected", False)
        serial_color = (90, 220, 120) if serial_connected else (80, 100, 230)
        row("RP2350 serial", "CONNECTED" if serial_connected else "OFFLINE", serial_color)

        section("Behavior")
        row("Emotion", status.get("emotion", "--"))
        row("Commanded face", status.get("face", "--"))
        row("AUTO face", status.get("auto_face", "--"))
        row("Decision", status.get("decision", "--"))
        row("Gesture", status.get("gesture", "--"))

        section("Angles")
        row("Commanded pan", self._safe_number(status.get("pan_angle"), 1, " deg"))
        row("Pan servo est.", self._safe_number(status.get("pan_servo_angle"), 1, " deg"))
        row("Commanded tilt", self._safe_number(status.get("tilt_angle"), 1, " deg"))
        row("AUTO pan", self._safe_number(status.get("auto_pan_angle"), 1, " deg"))
        row("AUTO tilt", self._safe_number(status.get("auto_tilt_angle"), 1, " deg"))
        row("Camera pan err", self._safe_number(status.get("pan_error_deg"), 2, " deg"))
        row("Camera tilt err", self._safe_number(status.get("tilt_error_deg"), 2, " deg"))

        section("Target")
        row("Source", status.get("target_type", "--"))
        row("Distance", self._safe_number(status.get("distance_m"), 2, " m"))
        row("Distance mode", status.get("distance_source", "--"))
        row("FPS", self._safe_number(status.get("fps"), 1))

        # Keep the key help anchored to the lower edge, independent of sections.
        footer_y = max(height - 58, y + 12)
        cv2.line(
            panel, (x_label, footer_y - 18), (panel_width - 18, footer_y - 18),
            (70, 77, 84), 1
        )
        cv2.putText(
            panel, "1:AUTO  2:MANUAL  3:ROS", (x_label, footer_y),
            font, 0.44, (150, 158, 166), 1, cv2.LINE_AA
        )
        cv2.putText(
            panel, "E: stop + MANUAL   Q: quit", (x_label, footer_y + 22),
            font, 0.44, (150, 158, 166), 1, cv2.LINE_AA
        )

        return np.hstack((frame, panel))

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