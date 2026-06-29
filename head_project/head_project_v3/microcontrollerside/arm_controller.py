from time import ticks_ms, ticks_diff

from servo_controller import ServoController


class ArmController:
    STATE_IDLE = "IDLE"
    STATE_RAISING = "RAISING"
    STATE_WAVING = "WAVING"
    STATE_LOWERING = "LOWERING"
    STATE_RUNNING = "RUNNING"

    def __init__(
        self,
        left_pin,
        right_pin,
        enabled=True,
        freq=50,
        min_us=500,
        max_us=2500,
        max_angle=180,

        left_neutral_angle=90,
        right_neutral_angle=90,

        left_up_angle=50,
        right_up_angle=130,

        left_min_limit_angle=20,
        left_max_limit_angle=160,

        right_min_limit_angle=20,
        right_max_limit_angle=160,

        step_deg=1.5,
        move_interval_ms=20,

        wave_amplitude_deg=7,
        wave_interval_ms=180,
        wave_cycles=4,

        use_right_arm_for_wave=False,

        running_amplitude_deg=30,
        running_interval_ms=110,
        running_use_right_arm=True
    ):
        self.enabled = enabled

        self.left_neutral_angle = left_neutral_angle
        self.right_neutral_angle = right_neutral_angle

        self.left_up_angle = left_up_angle
        self.right_up_angle = right_up_angle

        self.wave_amplitude_deg = wave_amplitude_deg
        self.wave_interval_ms = wave_interval_ms
        self.wave_cycles = wave_cycles
        self.use_right_arm_for_wave = use_right_arm_for_wave

        self.running_amplitude_deg = running_amplitude_deg
        self.running_interval_ms = running_interval_ms
        self.running_use_right_arm = running_use_right_arm

        self.running_requested = False

        self.state = self.STATE_IDLE

        self.wave_step = 0
        self.last_wave_time = ticks_ms()

        self.running_step = 0
        self.last_running_time = ticks_ms()

        right_servo_enabled = enabled and (
            use_right_arm_for_wave or running_use_right_arm
        )

        self.left_servo = ServoController(
            pin=left_pin,
            enabled=enabled,
            freq=freq,
            min_us=min_us,
            max_us=max_us,
            max_angle=max_angle,
            neutral_angle=left_neutral_angle,
            min_limit_angle=left_min_limit_angle,
            max_limit_angle=left_max_limit_angle,
            step_deg=step_deg,
            move_interval_ms=move_interval_ms
        )

        self.right_servo = ServoController(
            pin=right_pin,
            enabled=right_servo_enabled,
            freq=freq,
            min_us=min_us,
            max_us=max_us,
            max_angle=max_angle,
            neutral_angle=right_neutral_angle,
            min_limit_angle=right_min_limit_angle,
            max_limit_angle=right_max_limit_angle,
            step_deg=step_deg,
            move_interval_ms=move_interval_ms
        )

    # =====================================================
    # Public commands
    # =====================================================

    def start_wave(self):
        # Wave has priority over running.
        if self.state in (self.STATE_RAISING, self.STATE_WAVING):
            return

        self.state = self.STATE_RAISING
        self.wave_step = 0

        self.left_servo.set_target_angle(self.left_up_angle)

        if self.use_right_arm_for_wave:
            self.right_servo.set_target_angle(self.right_up_angle)

        print("ARM WAVE START")

    def set_running_active(self, active):
        self.running_requested = active

        if active:
            if self.state == self.STATE_IDLE:
                self._enter_running()
        else:
            if self.state == self.STATE_RUNNING:
                self.state = self.STATE_LOWERING
                self.left_servo.go_to_neutral()

                if self.running_use_right_arm:
                    self.right_servo.go_to_neutral()

    def center(self):
        self.running_requested = False
        self.state = self.STATE_LOWERING
        self.left_servo.go_to_neutral()

        if self.running_use_right_arm or self.use_right_arm_for_wave:
            self.right_servo.go_to_neutral()

    def stop(self):
        self.running_requested = False
        self.state = self.STATE_IDLE
        self.left_servo.hold_current_position()

        if self.running_use_right_arm or self.use_right_arm_for_wave:
            self.right_servo.hold_current_position()

    # =====================================================
    # Internal state helpers
    # =====================================================

    def _enter_running(self):
        self.state = self.STATE_RUNNING
        self.running_step = 0
        self.last_running_time = ticks_ms()
        print("ARM RUNNING START")

    def _both_at_target(self):
        left_ok = self.left_servo.is_at_target(tolerance=2.0)

        if not (self.use_right_arm_for_wave or self.running_use_right_arm):
            return left_ok

        right_ok = self.right_servo.is_at_target(tolerance=2.0)
        return left_ok and right_ok

    def _update_wave_motion(self):
        now = ticks_ms()

        if ticks_diff(now, self.last_wave_time) < self.wave_interval_ms:
            return

        self.last_wave_time = now

        sign = 1 if self.wave_step % 2 == 0 else -1

        left_target = self.left_up_angle + sign * self.wave_amplitude_deg
        self.left_servo.set_target_angle(left_target)

        if self.use_right_arm_for_wave:
            right_target = self.right_up_angle - sign * self.wave_amplitude_deg
            self.right_servo.set_target_angle(right_target)

        self.wave_step += 1

        if self.wave_step >= self.wave_cycles * 2:
            if self.running_requested:
                self._enter_running()
            else:
                self.state = self.STATE_LOWERING
                self.left_servo.go_to_neutral()

                if self.use_right_arm_for_wave:
                    self.right_servo.go_to_neutral()

    def _update_running_motion(self):
        now = ticks_ms()

        if ticks_diff(now, self.last_running_time) < self.running_interval_ms:
            return

        self.last_running_time = now

        sign = 1 if self.running_step % 2 == 0 else -1

        left_target = self.left_neutral_angle + sign * self.running_amplitude_deg
        right_target = self.right_neutral_angle - sign * self.running_amplitude_deg

        self.left_servo.set_target_angle(left_target)

        if self.running_use_right_arm:
            self.right_servo.set_target_angle(right_target)

        self.running_step += 1

    # =====================================================
    # Main update
    # =====================================================

    def update(self):
        self.left_servo.update()

        if self.use_right_arm_for_wave or self.running_use_right_arm:
            self.right_servo.update()

        if self.state == self.STATE_IDLE:
            if self.running_requested:
                self._enter_running()
            return

        if self.state == self.STATE_RAISING:
            if self._both_at_target():
                self.state = self.STATE_WAVING
                self.wave_step = 0
                self.last_wave_time = ticks_ms()

        elif self.state == self.STATE_WAVING:
            self._update_wave_motion()

        elif self.state == self.STATE_RUNNING:
            if not self.running_requested:
                self.state = self.STATE_LOWERING
                self.left_servo.go_to_neutral()

                if self.running_use_right_arm:
                    self.right_servo.go_to_neutral()
            else:
                self._update_running_motion()

        elif self.state == self.STATE_LOWERING:
            if self._both_at_target():
                self.state = self.STATE_IDLE
                print("ARM MOTION DONE")

                if self.running_requested:
                    self._enter_running()

    def deinit(self):
        self.left_servo.deinit()
        self.right_servo.deinit()