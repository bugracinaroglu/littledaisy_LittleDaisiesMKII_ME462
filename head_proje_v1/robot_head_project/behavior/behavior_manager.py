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
        no_human_face="SLEEPING"
    ):
        self.enable_head_tracking = enable_head_tracking
        self.enable_arm_wave = enable_arm_wave
        self.enable_lcd_face = enable_lcd_face

        self.head_servo_enabled = head_servo_enabled
        self.arm_servos_enabled = arm_servos_enabled
        self.lcd_enabled = lcd_enabled

        self.default_face = default_face
        self.no_human_face = no_human_face

        self.last_face_sent = None

    def _emotion_to_face(self, emotion_name, human_detected):
        if not human_detected:
            return self.no_human_face

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

        if e == "neutral":
            return "CURIOUS"

        return self.default_face

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

        human_detected = (
            human_result is not None and
            human_result.get("human_detected", False)
        )

        if (
            self.enable_head_tracking and
            self.head_servo_enabled and
            target is not None and
            target.get("valid", False) and
            head_mapping_result is not None
        ):
            head_angle = head_mapping_result["target_angle"]
            commands["head_angle"] = head_angle

            if command_sender is not None:
                command_sender.send_head_angle(head_angle)

        if self.enable_lcd_face and self.lcd_enabled:
            dominant_emotion = None

            if emotion_result is not None and emotion_result.get("ok", False):
                dominant_emotion = emotion_result.get("dominant", None)

            face = self._emotion_to_face(dominant_emotion, human_detected)
            commands["face"] = face

            if face != self.last_face_sent:
                if command_sender is not None:
                    command_sender.send_face(face)

                self.last_face_sent = face

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