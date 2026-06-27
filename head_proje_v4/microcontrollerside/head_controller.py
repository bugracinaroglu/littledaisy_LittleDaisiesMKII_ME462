from servo_controller import ServoController


class HeadController:
    def __init__(
        self,
        pin,
        enabled=True,
        freq=50,
        min_us=500,
        max_us=2500,
        max_angle=180,
        neutral_angle=90,
        min_limit_angle=0,
        max_limit_angle=180,
        step_deg=1.0,
        move_interval_ms=20
    ):
        self.servo = ServoController(
            pin=pin,
            enabled=enabled,
            freq=freq,
            min_us=min_us,
            max_us=max_us,
            max_angle=max_angle,
            neutral_angle=neutral_angle,
            min_limit_angle=min_limit_angle,
            max_limit_angle=max_limit_angle,
            step_deg=step_deg,
            move_interval_ms=move_interval_ms
        )

    def set_angle(self, angle):
        self.servo.set_target_angle(angle)

    def center(self):
        self.servo.go_to_neutral()

    def stop(self):
        self.servo.hold_current_position()

    def update(self):
        self.servo.update()

    def deinit(self):
        self.servo.deinit()