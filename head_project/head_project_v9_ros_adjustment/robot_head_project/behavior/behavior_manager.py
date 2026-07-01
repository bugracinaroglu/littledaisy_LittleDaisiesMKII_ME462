import time

from control.control_mode import ControlMode


class BehaviorManager:
    def __init__(
        self,
        enable_head_tracking=True,
        enable_arm_wave=True,
        enable_lcd_face=True,
        head_pan_servo_enabled=True,
        head_tilt_servo_enabled=True,
        arm_servos_enabled=True,
        lcd_enabled=True,
        default_face="CURIOUS",
        no_human_face="SLEEPING",
        no_human_sleep_delay_sec=3.0,
    ):
        self.enable_head_tracking = enable_head_tracking
        self.enable_arm_wave = enable_arm_wave
        self.enable_lcd_face = enable_lcd_face
        self.head_pan_servo_enabled = head_pan_servo_enabled
        self.head_tilt_servo_enabled = head_tilt_servo_enabled
        self.arm_servos_enabled = arm_servos_enabled
        self.lcd_enabled = lcd_enabled
        self.default_face = default_face
        self.no_human_face = no_human_face
        self.no_human_sleep_delay_sec = no_human_sleep_delay_sec

        self.last_face_sent = None
        self.last_human_seen_time = time.monotonic()
        self.last_control_mode = None

    def _emotion_to_face(self, emotion_name):
        if emotion_name is None:
            return self.default_face

        mapping = {
            "happy": "HAPPY",
            "sad": "SAD",
            "angry": "ANGRY",
            "surprise": "SURPRISED",
            "disgust": "DISGUST",
            "neutral": "NEUTRAL",
        }
        return mapping.get(str(emotion_name).lower(), self.default_face)

    @staticmethod
    def _get_human_detected(human_result, target):
        if human_result is None:
            return False
        if not human_result.get("human_detected", False):
            return False
        return target is not None and target.get("valid", False)

    def on_control_mode_changed(self, _old_mode, new_mode):
        new_mode = ControlMode.normalize(new_mode)
        if new_mode == ControlMode.AUTO:
            self.last_face_sent = None
            self.last_human_seen_time = time.monotonic()
        self.last_control_mode = new_mode

    def _handle_mode_change(self, control_mode):
        if control_mode == self.last_control_mode:
            return

        # Re-send the current automatic face whenever AUTO regains authority.
        # Otherwise the face could remain at the last MANUAL/ROS command.
        if control_mode == ControlMode.AUTO:
            self.last_face_sent = None
            self.last_human_seen_time = time.monotonic()

        self.last_control_mode = control_mode

    def update(
        self,
        target,
        head_mapping_result,
        human_result,
        emotion_result,
        gesture_result,
        robot_head,
        control_mode,
    ):
        control_mode = ControlMode.normalize(control_mode)
        self._handle_mode_change(control_mode)
        auto_commands_active = control_mode == ControlMode.AUTO

        commands = {
            "auto_commands_active": auto_commands_active,
            "head_pan_angle": None,
            "head_tilt_angle": None,
            "face": None,
            "arm_wave": False,
        }

        now = time.monotonic()
        human_detected = self._get_human_detected(human_result, target)
        if human_detected:
            self.last_human_seen_time = now

        sleeping_due_to_no_human = (
            not human_detected
            and now - self.last_human_seen_time
            >= self.no_human_sleep_delay_sec
        )

        if (
            self.enable_head_tracking
            and self.head_pan_servo_enabled
            and human_detected
            and head_mapping_result is not None
        ):
            pan_angle = head_mapping_result["pan_angle"]
            tilt_angle = head_mapping_result["tilt_angle"]
            commands["head_pan_angle"] = pan_angle
            commands["head_tilt_angle"] = tilt_angle

            if auto_commands_active and robot_head is not None:
                robot_head.set_head_pose(
                    pan_angle,
                    tilt_angle,
                    source=ControlMode.AUTO,
                )

        if self.enable_lcd_face and self.lcd_enabled:
            if sleeping_due_to_no_human:
                face = self.no_human_face
            else:
                dominant_emotion = None
                if emotion_result is not None and emotion_result.get("ok", False):
                    dominant_emotion = emotion_result.get("dominant")
                face = self._emotion_to_face(dominant_emotion)

            commands["face"] = face
            if auto_commands_active and face != self.last_face_sent:
                sent = False
                if robot_head is not None:
                    sent = robot_head.show_face(
                        face,
                        source=ControlMode.AUTO,
                    )
                if sent:
                    self.last_face_sent = face
                    print("[Face command]:", face)

        if (
            self.enable_arm_wave
            and self.arm_servos_enabled
            and gesture_result is not None
            and gesture_result.get("hello_event", False)
        ):
            commands["arm_wave"] = True
            if auto_commands_active and robot_head is not None:
                robot_head.wave_arm(source=ControlMode.AUTO)

        return commands
