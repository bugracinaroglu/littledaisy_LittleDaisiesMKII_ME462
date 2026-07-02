from time import ticks_ms, ticks_diff


class HeadGestureController:
    """Non-blocking RP2350 head-motion sequencer.

    Repeat-count meanings:
      * NOD: one down/up pair.
      * SHAKE / LOOK_AROUND: one left/right pair.
      * DANCE / DAISY_DANCE: one right-centre-left-centre dance cycle.
      * GREET: number of nods performed on EACH side.

    The original head pose is restored at the end of every moving gesture.
    """

    VALID_GESTURES = (
        "NOD",
        "SUNGLASSES_NOD",
        "SIGMA_NOD",
        "SHAKE",
        "LOOK_AROUND",
        "CELEBRATE",
        "DANCE",
        "GREET",
        "DAISY_DANCE",
        "SLEEP",
        "WAKE_UP",
    )

    def __init__(
        self,
        head,
        arms=None,
        default_repeat_count=3,
        max_repeat_count=8,
        target_tolerance_deg=1.0,
        center_before_start=True,
        center_dwell_ms=250,
        nod_up_offset_deg=10.0,
        nod_down_offset_deg=-10.0,
        nod_dwell_ms=120,
        shake_left_offset_deg=-8.0,
        shake_right_offset_deg=8.0,
        shake_dwell_ms=130,
        look_around_use_full_range=True,
        look_left_offset_deg=-18.0,
        look_right_offset_deg=18.0,
        look_dwell_ms=320,
        wake_up_tilt_offset_deg=6.0,
        wake_up_dwell_ms=220,
        dance_pan_offset_deg=30.0,
        dance_tilt_up_offset_deg=9.0,
        dance_tilt_down_offset_deg=-9.0,
        dance_dwell_ms=150,
        greet_pan_offset_deg=35.0,
        greet_nod_up_offset_deg=9.0,
        greet_nod_down_offset_deg=-9.0,
        greet_turn_dwell_ms=260,
        greet_nod_dwell_ms=130,
    ):
        self.head = head
        self.arms = arms
        self.default_repeat_count = max(1, int(default_repeat_count))
        self.max_repeat_count = max(1, int(max_repeat_count))
        self.target_tolerance_deg = max(0.1, float(target_tolerance_deg))
        self.center_before_start = bool(center_before_start)
        self.center_dwell_ms = max(0, int(center_dwell_ms))

        self.nod_up_offset_deg = float(nod_up_offset_deg)
        self.nod_down_offset_deg = float(nod_down_offset_deg)
        self.nod_dwell_ms = max(0, int(nod_dwell_ms))

        self.shake_left_offset_deg = float(shake_left_offset_deg)
        self.shake_right_offset_deg = float(shake_right_offset_deg)
        self.shake_dwell_ms = max(0, int(shake_dwell_ms))

        self.look_around_use_full_range = bool(look_around_use_full_range)
        self.look_left_offset_deg = float(look_left_offset_deg)
        self.look_right_offset_deg = float(look_right_offset_deg)
        self.look_dwell_ms = max(0, int(look_dwell_ms))

        self.wake_up_tilt_offset_deg = float(wake_up_tilt_offset_deg)
        self.wake_up_dwell_ms = max(0, int(wake_up_dwell_ms))

        self.dance_pan_offset_deg = abs(float(dance_pan_offset_deg))
        self.dance_tilt_up_offset_deg = float(dance_tilt_up_offset_deg)
        self.dance_tilt_down_offset_deg = float(dance_tilt_down_offset_deg)
        self.dance_dwell_ms = max(0, int(dance_dwell_ms))

        self.greet_pan_offset_deg = abs(float(greet_pan_offset_deg))
        self.greet_nod_up_offset_deg = float(greet_nod_up_offset_deg)
        self.greet_nod_down_offset_deg = float(greet_nod_down_offset_deg)
        self.greet_turn_dwell_ms = max(0, int(greet_turn_dwell_ms))
        self.greet_nod_dwell_ms = max(0, int(greet_nod_dwell_ms))

        self.active = False
        self.name = None
        self.steps = []
        self.step_index = 0
        self.arrived_ms = None
        self.active_repeat_count = self.default_repeat_count

    def _normalize_count(self, count):
        try:
            count = int(count)
        except Exception:
            count = self.default_repeat_count

        if count <= 0:
            count = self.default_repeat_count
        return min(count, self.max_repeat_count)

    @staticmethod
    def _step(axis, value, dwell_ms):
        axis = str(axis).strip().upper()
        if axis == "POSE":
            value = (float(value[0]), float(value[1]))
        elif axis == "ACTION":
            value = str(value).strip().upper()
        else:
            value = float(value)
        return (axis, value, max(0, int(dwell_ms)))

    CENTERED_GESTURES = (
        "NOD",
        "SUNGLASSES_NOD",
        "SIGMA_NOD",
        "SHAKE",
        "LOOK_AROUND",
        "CELEBRATE",
        "DANCE",
        "GREET",
        "DAISY_DANCE",
    )

    def _uses_centered_start(self, name):
        return self.center_before_start and name in self.CENTERED_GESTURES

    def _prepend_center_and_action(self, name, steps):
        prefix = []
        if self._uses_centered_start(name):
            prefix.append(
                self._step(
                    "POSE",
                    (
                        self.head.pan_head_neutral_angle,
                        self.head.tilt_neutral_angle,
                    ),
                    self.center_dwell_ms,
                )
            )

        # Arm choreography starts only after centering has completed.
        if name == "CELEBRATE":
            prefix.append(self._step("ACTION", "ARM_WAVE", 0))
        elif name == "DAISY_DANCE":
            prefix.append(self._step("ACTION", "ARM_DANCE", 0))

        return prefix + steps

    def _build_nod_steps(self, repeat_count, base_tilt):
        steps = []
        down = self.head.clamp_tilt_angle(
            base_tilt + self.nod_down_offset_deg
        )
        up = self.head.clamp_tilt_angle(
            base_tilt + self.nod_up_offset_deg
        )

        for _ in range(repeat_count):
            steps.append(self._step("TILT", down, self.nod_dwell_ms))
            steps.append(self._step("TILT", up, self.nod_dwell_ms))

        steps.append(self._step("TILT", base_tilt, self.nod_dwell_ms))
        return steps

    def _build_shake_steps(self, repeat_count, base_pan, dwell_ms, left, right):
        steps = []
        left_target = self.head.clamp_pan_head_angle(base_pan + left)
        right_target = self.head.clamp_pan_head_angle(base_pan + right)

        for _ in range(repeat_count):
            steps.append(self._step("PAN", left_target, dwell_ms))
            steps.append(self._step("PAN", right_target, dwell_ms))

        steps.append(self._step("PAN", base_pan, dwell_ms))
        return steps

    def _build_look_around_steps(self, repeat_count, base_pan):
        if not self.look_around_use_full_range:
            return self._build_shake_steps(
                repeat_count,
                base_pan,
                self.look_dwell_ms,
                self.look_left_offset_deg,
                self.look_right_offset_deg,
            )

        left_limit, right_limit = self.head.get_reachable_pan_head_limits()
        steps = []
        for _ in range(repeat_count):
            steps.append(self._step("PAN", left_limit, self.look_dwell_ms))
            steps.append(self._step("PAN", right_limit, self.look_dwell_ms))
        steps.append(self._step("PAN", base_pan, self.look_dwell_ms))
        return steps

    def _build_dance_steps(self, repeat_count, base_pan, base_tilt):
        """Sway right/left while tilt moves simultaneously like a beat."""
        steps = []
        right = self.head.clamp_pan_head_angle(
            base_pan + self.dance_pan_offset_deg
        )
        left = self.head.clamp_pan_head_angle(
            base_pan - self.dance_pan_offset_deg
        )
        up = self.head.clamp_tilt_angle(
            base_tilt + self.dance_tilt_up_offset_deg
        )
        down = self.head.clamp_tilt_angle(
            base_tilt + self.dance_tilt_down_offset_deg
        )

        for _ in range(repeat_count):
            steps.append(self._step("POSE", (right, up), self.dance_dwell_ms))
            steps.append(self._step("POSE", (base_pan, down), self.dance_dwell_ms))
            steps.append(self._step("POSE", (left, up), self.dance_dwell_ms))
            steps.append(self._step("POSE", (base_pan, down), self.dance_dwell_ms))

        steps.append(self._step("POSE", (base_pan, base_tilt), self.dance_dwell_ms))
        return steps

    def _append_side_greeting(self, steps, side_pan, nod_count, base_tilt):
        down = self.head.clamp_tilt_angle(
            base_tilt + self.greet_nod_down_offset_deg
        )
        up = self.head.clamp_tilt_angle(
            base_tilt + self.greet_nod_up_offset_deg
        )

        steps.append(
            self._step("POSE", (side_pan, base_tilt), self.greet_turn_dwell_ms)
        )
        for _ in range(nod_count):
            steps.append(
                self._step("POSE", (side_pan, down), self.greet_nod_dwell_ms)
            )
            steps.append(
                self._step("POSE", (side_pan, up), self.greet_nod_dwell_ms)
            )
        steps.append(
            self._step("POSE", (side_pan, base_tilt), self.greet_nod_dwell_ms)
        )

    def _build_greet_steps(self, nod_count, base_pan, base_tilt):
        """Turn right, nod; turn left, nod; then restore the original pose."""
        steps = []
        right = self.head.clamp_pan_head_angle(
            base_pan + self.greet_pan_offset_deg
        )
        left = self.head.clamp_pan_head_angle(
            base_pan - self.greet_pan_offset_deg
        )

        self._append_side_greeting(steps, right, nod_count, base_tilt)
        self._append_side_greeting(steps, left, nod_count, base_tilt)
        steps.append(
            self._step("POSE", (base_pan, base_tilt), self.greet_turn_dwell_ms)
        )
        return steps

    def start(self, name, count=None):
        name = str(name).strip().upper()
        if name not in self.VALID_GESTURES:
            print("Unsupported gesture:", name)
            return False

        repeat_count = self._normalize_count(count)
        if self._uses_centered_start(name):
            base_pan = self.head.pan_head_neutral_angle
            base_tilt = self.head.tilt_neutral_angle
        else:
            base_pan = self.head.get_current_pan_head_angle()
            base_tilt = self.head.get_current_tilt_angle()

        if name in ("NOD", "SUNGLASSES_NOD", "SIGMA_NOD", "CELEBRATE"):
            steps = self._build_nod_steps(repeat_count, base_tilt)
        elif name == "SHAKE":
            steps = self._build_shake_steps(
                repeat_count,
                base_pan,
                self.shake_dwell_ms,
                self.shake_left_offset_deg,
                self.shake_right_offset_deg,
            )
        elif name == "LOOK_AROUND":
            steps = self._build_look_around_steps(repeat_count, base_pan)
        elif name in ("DANCE", "DAISY_DANCE"):
            steps = self._build_dance_steps(repeat_count, base_pan, base_tilt)
        elif name == "GREET":
            steps = self._build_greet_steps(repeat_count, base_pan, base_tilt)
        elif name == "SLEEP":
            steps = [
                self._step("PAN", self.head.pan_head_neutral_angle, 0),
                self._step("TILT", self.head.tilt_neutral_angle, 250),
            ]
        elif name == "WAKE_UP":
            wake_tilt = self.head.clamp_tilt_angle(
                base_tilt + self.wake_up_tilt_offset_deg
            )
            steps = [
                self._step("TILT", wake_tilt, self.wake_up_dwell_ms),
                self._step("TILT", base_tilt, self.wake_up_dwell_ms),
            ]
        else:
            return False

        steps = self._prepend_center_and_action(name, steps)

        self.cancel(hold_position=False)
        self.name = name
        self.steps = steps
        self.step_index = 0
        self.arrived_ms = None
        self.active_repeat_count = repeat_count
        self.active = bool(steps)

        if self.active:
            print("Gesture start: {} x{}".format(name, repeat_count))
            self._apply_current_step()
        return self.active

    def cancel(self, hold_position=True):
        was_active = self.active
        cancelled_name = self.name
        self.active = False
        self.name = None
        self.steps = []
        self.step_index = 0
        self.arrived_ms = None

        if cancelled_name in ("CELEBRATE", "DAISY_DANCE") and self.arms is not None:
            self.arms.center()
        self.active_repeat_count = self.default_repeat_count

        if was_active and hold_position and self.head is not None:
            self.head.stop()
            print("Gesture cancelled.")
        return was_active

    def is_active(self):
        return self.active

    def get_active_name(self):
        return self.name if self.active else None

    def _apply_current_step(self):
        if not self.active or self.step_index >= len(self.steps):
            return

        axis, value, _dwell_ms = self.steps[self.step_index]
        self.arrived_ms = None

        if axis == "PAN":
            self.head.set_pan(value)
        elif axis == "TILT":
            self.head.set_tilt(value)
        elif axis == "POSE":
            self.head.set_pose(value[0], value[1])
        elif axis == "ACTION" and self.arms is not None:
            if value == "ARM_WAVE":
                self.arms.start_wave()
            elif value == "ARM_DANCE":
                self.arms.start_dance(self.active_repeat_count)

    def _current_step_reached(self):
        axis, _value, _dwell_ms = self.steps[self.step_index]
        if axis == "PAN":
            return self.head.is_pan_at_target(self.target_tolerance_deg)
        if axis == "TILT":
            return self.head.is_tilt_at_target(self.target_tolerance_deg)
        if axis == "POSE":
            return self.head.is_at_target(self.target_tolerance_deg)
        if axis == "ACTION":
            return True
        return True

    def update(self):
        if not self.active:
            return False

        now = ticks_ms()
        _axis, _value, dwell_ms = self.steps[self.step_index]

        if not self._current_step_reached():
            self.arrived_ms = None
            return True

        if self.arrived_ms is None:
            self.arrived_ms = now
            return True

        if ticks_diff(now, self.arrived_ms) < dwell_ms:
            return True

        self.step_index += 1
        if self.step_index >= len(self.steps):
            completed_name = self.name
            self.active = False
            self.name = None
            self.steps = []
            self.arrived_ms = None
            self.active_repeat_count = self.default_repeat_count
            if completed_name == "DAISY_DANCE" and self.arms is not None:
                self.arms.center()
            print("Gesture complete:", completed_name)
            return False

        self._apply_current_step()
        return True
