from control.control_mode import ControlMode


class ManualController:
    """Keyboard/direct-manual target state for pan and tilt."""

    def __init__(
        self,
        robot_head,
        pan_center_angle,
        tilt_center_angle,
        pan_step_deg=5.0,
        tilt_step_deg=2.0,
    ):
        self.robot_head = robot_head
        self.pan_angle = float(pan_center_angle)
        self.tilt_angle = float(tilt_center_angle)
        self.pan_step_deg = float(pan_step_deg)
        self.tilt_step_deg = float(tilt_step_deg)

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
