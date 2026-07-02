from math import sqrt
from time import ticks_ms, ticks_diff

try:
    from machine import Pin, PWM
except ImportError:
    Pin = None
    PWM = None


class ServoController:
    """Non-blocking servo controller.

    Two motion modes are supported:

    * Smooth mode: enabled when max_speed_deg_s and acceleration_deg_s2 are
      both positive. Motion is time based, accelerates gradually and slows
      automatically near the target.
    * Legacy step mode: used when smooth parameters are omitted. This keeps
      older arm-controller behaviour compatible.
    """

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
        move_interval_ms=20,
        max_speed_deg_s=None,
        acceleration_deg_s2=None,
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

        self.step_deg = max(0.001, float(step_deg))
        self.move_interval_ms = max(1, int(move_interval_ms))
        self.max_speed_deg_s = (
            None if max_speed_deg_s is None else max(0.0, float(max_speed_deg_s))
        )
        self.acceleration_deg_s2 = (
            None
            if acceleration_deg_s2 is None
            else max(0.0, float(acceleration_deg_s2))
        )
        self.smooth_motion_enabled = bool(
            self.max_speed_deg_s
            and self.acceleration_deg_s2
            and self.max_speed_deg_s > 0.0
            and self.acceleration_deg_s2 > 0.0
        )

        self.last_move_time = ticks_ms()
        self.current_velocity_deg_s = 0.0

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
        angle = max(0, min(float(angle), self.max_angle))
        angle = max(self.min_limit_angle, min(angle, self.max_limit_angle))
        return angle

    def _angle_to_duty_ns(self, angle):
        angle = self._clamp_angle(angle)

        pulse_us = self.min_us + (angle / self.max_angle) * (
            self.max_us - self.min_us
        )
        return int(pulse_us * 1000)

    def _write_angle(self, angle):
        if not self.enabled or self.pwm is None:
            return

        self.pwm.duty_ns(self._angle_to_duty_ns(angle))

    @staticmethod
    def _move_towards(value, target, max_delta):
        if value < target:
            return min(value + max_delta, target)
        if value > target:
            return max(value - max_delta, target)
        return target

    def go_to_angle_immediate(self, angle):
        angle = self._clamp_angle(angle)

        self.current_angle = angle
        self.target_angle = angle
        self.current_velocity_deg_s = 0.0
        self.last_move_time = ticks_ms()

        self._write_angle(angle)

    def set_target_angle(self, angle):
        self.target_angle = self._clamp_angle(angle)

    def go_to_neutral(self):
        self.set_target_angle(self.neutral_angle)

    def hold_current_position(self):
        self.target_angle = self.current_angle
        self.current_velocity_deg_s = 0.0

    def is_at_target(self, tolerance=1.0):
        return abs(self.target_angle - self.current_angle) <= tolerance

    def _update_legacy_step(self):
        error = self.target_angle - self.current_angle

        if abs(error) <= self.step_deg:
            self.current_angle = self.target_angle
        elif error > 0:
            self.current_angle += self.step_deg
        else:
            self.current_angle -= self.step_deg

        self.current_velocity_deg_s = 0.0
        self.current_angle = self._clamp_angle(self.current_angle)
        self._write_angle(self.current_angle)

    def _update_smooth(self, elapsed_ms):
        error = self.target_angle - self.current_angle
        if abs(error) <= 0.001:
            self.current_angle = self.target_angle
            self.current_velocity_deg_s = 0.0
            self._write_angle(self.current_angle)
            return

        # Cap a delayed loop iteration so one long LCD/serial pause cannot
        # create one large physical jump when execution resumes.
        dt_s = min(max(elapsed_ms / 1000.0, 0.001), 0.100)
        direction = 1.0 if error > 0.0 else -1.0
        distance = abs(error)

        # sqrt(2*a*d) is the maximum speed from which the axis can still stop
        # over the remaining distance. It produces a trapezoidal/triangular
        # profile without blocking the main loop.
        braking_limited_speed = sqrt(
            max(0.0, 2.0 * self.acceleration_deg_s2 * distance)
        )
        desired_speed = min(self.max_speed_deg_s, braking_limited_speed)
        desired_velocity = direction * desired_speed

        max_velocity_change = self.acceleration_deg_s2 * dt_s
        self.current_velocity_deg_s = self._move_towards(
            self.current_velocity_deg_s,
            desired_velocity,
            max_velocity_change,
        )

        movement = self.current_velocity_deg_s * dt_s
        if abs(movement) >= distance or movement * error <= 0.0:
            # movement*error <= 0 can occur briefly after an abrupt target
            # reversal. Continue decelerating but never move away indefinitely.
            if abs(movement) >= distance:
                self.current_angle = self.target_angle
                self.current_velocity_deg_s = 0.0
            else:
                self.current_angle += movement
        else:
            self.current_angle += movement

        # Prevent numerical overshoot after target reversals.
        new_error = self.target_angle - self.current_angle
        if error * new_error <= 0.0:
            self.current_angle = self.target_angle
            self.current_velocity_deg_s = 0.0

        self.current_angle = self._clamp_angle(self.current_angle)
        self._write_angle(self.current_angle)

    def update(self):
        now = ticks_ms()
        elapsed_ms = ticks_diff(now, self.last_move_time)

        if elapsed_ms < self.move_interval_ms:
            return

        self.last_move_time = now

        if self.smooth_motion_enabled:
            self._update_smooth(elapsed_ms)
        else:
            self._update_legacy_step()

    def deinit(self):
        if self.pwm is not None:
            self.pwm.deinit()
            self.pwm = None
