import time


class BehaviorManager:
    def __init__(
        self,
        enable_head_tracking=True,
        enable_arm_wave=True,
        enable_lcd_face=True,
        head_servo_enabled=True,
        arm_servos_enabled=True,
        lcd_enabled=True,
        default_face="CURIOUS",
        no_human_face="SLEEPING",
        no_human_sleep_delay_sec=3.0
    ):
        self.enable_head_tracking = enable_head_tracking
        self.enable_arm_wave = enable_arm_wave
        self.enable_lcd_face = enable_lcd_face

        self.head_servo_enabled = head_servo_enabled
        self.arm_servos_enabled = arm_servos_enabled
        self.lcd_enabled = lcd_enabled

        self.default_face = default_face
        self.no_human_face = no_human_face
        self.no_human_sleep_delay_sec = no_human_sleep_delay_sec

        self.last_face_sent = None
        self.last_human_seen_time = time.monotonic()

    def _emotion_to_face(self, emotion_name):
        if emotion_name is None:
            return self.default_face

        e = emotion_name.lower()

        if e == "happy":
            return "HAPPY"

        if e == "sad":
            return "SAD"

        if e == "angry":
            return "ANGRY"

        if e == "surprise":
            return "SURPRISED"

        if e == "disgust":
            return "DISGUST"

        if e == "neutral":
            return "NEUTRAL"

        return self.default_face

    def _get_human_detected(self, human_result, target):
        """
        Human detected kararını daha güvenli yapıyoruz.

        human_result bazen yanlış pozitif verebilir.
        Bu yüzden target geçerli mi diye de bakıyoruz.
        """

        if human_result is None:
            return False

        if not human_result.get("human_detected", False):
            return False

        if target is None or not target.get("valid", False):
            return False

        target_type = target.get("target_type", "none")

        # Bunlar gerçek insan/body tracking için daha güvenilir.
        reliable_targets = [
            "torso",
            "upper_body",
            "body",
            "face_fallback",
            "emotion_face"
        ]

        return target_type in reliable_targets

    def update(
        self,
        target,
        head_mapping_result,
        human_result,
        emotion_result,
        gesture_result,
        command_sender
    ):
        commands = {
            "head_angle": None,
            "face": None,
            "arm_wave": False
        }

        now = time.monotonic()

        human_detected = self._get_human_detected(human_result, target)

        if human_detected:
            self.last_human_seen_time = now

        no_human_duration = now - self.last_human_seen_time
        sleeping_due_to_no_human = (
            not human_detected and
            no_human_duration >= self.no_human_sleep_delay_sec
        )

        # -----------------------------
        # Head tracking
        # -----------------------------
        if (
            self.enable_head_tracking and
            self.head_servo_enabled and
            human_detected and
            target is not None and
            target.get("valid", False) and
            head_mapping_result is not None
        ):
            head_angle = head_mapping_result["target_angle"]
            commands["head_angle"] = head_angle

            if command_sender is not None:
                command_sender.send_head_angle(head_angle)

        # -----------------------------
        # LCD face
        # -----------------------------
        if self.enable_lcd_face and self.lcd_enabled:
            if sleeping_due_to_no_human:
                face = self.no_human_face
            else:
                dominant_emotion = None

                if emotion_result is not None and emotion_result.get("ok", False):
                    dominant_emotion = emotion_result.get("dominant", None)

                face = self._emotion_to_face(dominant_emotion)

            commands["face"] = face

            if face != self.last_face_sent:
                if command_sender is not None:
                    command_sender.send_face(face)

                self.last_face_sent = face
                print("[Face command]:", face)

        # -----------------------------
        # Arm wave
        # -----------------------------
        if (
            self.enable_arm_wave and
            self.arm_servos_enabled and
            gesture_result is not None and
            gesture_result.get("hello_event", False)
        ):
            commands["arm_wave"] = True

            if command_sender is not None:
                command_sender.send_arm_wave()

        return commands