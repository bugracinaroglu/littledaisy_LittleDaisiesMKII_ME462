from time import ticks_ms, ticks_diff

try:
    from machine import Pin, PWM
except ImportError:
    Pin = None
    PWM = None


class ServoController:
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
        self.pin = pin
        self.enabled = enabled

        self.freq = freq
        self.min_us = min_us
        self.max_us = max_us
        self.max_angle = max_angle

        self.neutral_angle = neutral_angle
        self.min_limit_angle = min_limit_angle
        self.max_limit_angle = max_limit_angle

        self.step_deg = step_deg
        self.move_interval_ms = move_interval_ms
        self.last_move_time = ticks_ms()

        self.current_angle = self._clamp_angle(neutral_angle)
        self.target_angle = self.current_angle

        self.pwm = None

        if self.enabled:
            self._init_pwm()
            self.go_to_angle_immediate(self.current_angle)

    def _init_pwm(self):
        if PWM is None or Pin is None:
            print("PWM/Pin not available. Servo disabled.")
            self.enabled = False
            return

        self.pwm = PWM(Pin(self.pin))
        self.pwm.freq(self.freq)

    def _clamp_angle(self, angle):
        angle = max(0, min(angle, self.max_angle))
        angle = max(self.min_limit_angle, min(angle, self.max_limit_angle))
        return angle

    def _angle_to_duty_ns(self, angle):
        angle = self._clamp_angle(angle)

        pulse_us = self.min_us + (angle / self.max_angle) * (self.max_us - self.min_us)
        return int(pulse_us * 1000)

    def _write_angle(self, angle):
        if not self.enabled or self.pwm is None:
            return

        self.pwm.duty_ns(self._angle_to_duty_ns(angle))

    def go_to_angle_immediate(self, angle):
        angle = self._clamp_angle(angle)

        self.current_angle = angle
        self.target_angle = angle

        self._write_angle(angle)

    def set_target_angle(self, angle):
        self.target_angle = self._clamp_angle(angle)

    def go_to_neutral(self):
        self.set_target_angle(self.neutral_angle)

    def hold_current_position(self):
        self.target_angle = self.current_angle

    def is_at_target(self, tolerance=1.0):
        return abs(self.target_angle - self.current_angle) <= tolerance

    def update(self):
        now = ticks_ms()

        if ticks_diff(now, self.last_move_time) < self.move_interval_ms:
            return

        self.last_move_time = now

        error = self.target_angle - self.current_angle

        if abs(error) <= self.step_deg:
            self.current_angle = self.target_angle

        elif error > 0:
            self.current_angle += self.step_deg

        else:
            self.current_angle -= self.step_deg

        self.current_angle = self._clamp_angle(self.current_angle)
        self._write_angle(self.current_angle)

    def deinit(self):
        if self.pwm is not None:
            self.pwm.deinit()
            self.pwm = None