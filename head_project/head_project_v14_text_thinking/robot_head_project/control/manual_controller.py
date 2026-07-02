from control.control_mode import ControlMode


class ManualController:
    """Keyboard/direct-manual controls for pose, faces and RP2350 gestures."""

    def __init__(
        self,
        robot_head,
        pan_center_angle,
        tilt_center_angle,
        pan_step_deg=5.0,
        tilt_step_deg=2.0,
        gesture_count=3,
        face_hold_ms=4000,
        text_hold_ms=5000,
        manual_text="Hello from Daisy",
        manual_text_italic=False,
        oopsie_hold_ms=5000,
    ):
        self.robot_head = robot_head
        self.pan_angle = float(pan_center_angle)
        self.tilt_angle = float(tilt_center_angle)
        self.pan_step_deg = float(pan_step_deg)
        self.tilt_step_deg = float(tilt_step_deg)
        self.gesture_count = max(1, int(gesture_count))
        self.face_hold_ms = max(0, int(face_hold_ms))
        self.text_hold_ms = max(0, int(text_hold_ms))
        self.manual_text = str(manual_text)
        self.manual_text_italic = bool(manual_text_italic)
        self.oopsie_hold_ms = max(0, int(oopsie_hold_ms))

    def sync_from_robot_status(self):
        status = self.robot_head.get_status()
        if status.get("last_pan_angle") is not None:
            self.pan_angle = float(status["last_pan_angle"])
        if status.get("last_tilt_angle") is not None:
            self.tilt_angle = float(status["last_tilt_angle"])

    def send_pose(self):
        self.pan_angle = max(
            self.robot_head.pan_min_angle,
            min(self.pan_angle, self.robot_head.pan_max_angle),
        )
        self.tilt_angle = max(
            self.robot_head.tilt_min_angle,
            min(self.tilt_angle, self.robot_head.tilt_max_angle),
        )

        sent = self.robot_head.set_head_pose(
            self.pan_angle,
            self.tilt_angle,
            source=ControlMode.MANUAL,
        )
        if sent:
            status = self.robot_head.get_status()
            self.pan_angle = status.get("last_pan_angle", self.pan_angle)
            self.tilt_angle = status.get("last_tilt_angle", self.tilt_angle)
        return sent

    def pan_left(self):
        self.pan_angle -= self.pan_step_deg
        return self.send_pose()

    def pan_right(self):
        self.pan_angle += self.pan_step_deg
        return self.send_pose()

    def tilt_up(self):
        self.tilt_angle += self.tilt_step_deg
        return self.send_pose()

    def tilt_down(self):
        self.tilt_angle -= self.tilt_step_deg
        return self.send_pose()

    def center(self):
        sent = self.robot_head.center(source=ControlMode.MANUAL)
        if sent:
            self.sync_from_robot_status()
        return sent

    def show_sigma(self):
        return self.robot_head.show_face(
            "SIGMA",
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def show_sunglasses(self):
        return self.robot_head.show_face(
            "SUNGLASSES",
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def show_thinking(self):
        return self.robot_head.show_thinking(
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def show_oopsie_daisy(self):
        return self.robot_head.show_oopsie_daisy(
            hold_ms=self.oopsie_hold_ms,
            source=ControlMode.MANUAL,
        )

    def show_manual_text(self):
        return self.robot_head.show_text(
            self.manual_text,
            hold_ms=self.text_hold_ms,
            italic=self.manual_text_italic,
            source=ControlMode.MANUAL,
        )

    def nod(self):
        return self.robot_head.nod_head(
            count=self.gesture_count,
            source=ControlMode.MANUAL,
        )

    def sunglasses_nod(self):
        return self.robot_head.sunglasses_nod(
            count=self.gesture_count,
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def sigma_nod(self):
        return self.robot_head.sigma_nod(
            count=self.gesture_count,
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def shake(self):
        return self.robot_head.shake_head(
            count=self.gesture_count,
            source=ControlMode.MANUAL,
        )

    def look_around(self):
        return self.robot_head.look_around(
            count=1,
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def celebrate(self):
        return self.robot_head.celebrate(
            count=self.gesture_count,
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def dance(self):
        return self.robot_head.dance(
            count=self.gesture_count,
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def greet(self):
        return self.robot_head.greet(
            nod_count=self.gesture_count,
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def daisy_dance(self):
        return self.robot_head.daisy_dance(
            count=self.gesture_count,
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def sleep(self):
        return self.robot_head.sleep(
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def wake_up(self):
        return self.robot_head.wake_up(
            hold_ms=self.face_hold_ms,
            source=ControlMode.MANUAL,
        )

    def cancel_gesture(self):
        return self.robot_head.cancel_gesture(source=ControlMode.MANUAL)
