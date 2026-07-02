from time import ticks_ms, ticks_diff


class HeadGestureController:
    """Non-blocking RP2350 head-motion sequencer.

    One repeat of NOD means one down/up pair. One repeat of SHAKE means one
    left/right pair. The original head position is restored at the end.
    """

    VALID_GESTURES = (
        "NOD",
        "SUNGLASSES_NOD",
        "SIGMA_NOD",
        "SHAKE",
        "LOOK_AROUND",
        "CELEBRATE",
        "SLEEP",
        "WAKE_UP",
    )

    def __init__(
        self,
        head,
        arms=None,
        default_repeat_count=2,
        max_repeat_count=8,
        target_tolerance_deg=1.0,
        nod_up_offset_deg=7.0,
        nod_down_offset_deg=-7.0,
        nod_dwell_ms=120,
        shake_left_offset_deg=-8.0,
        shake_right_offset_deg=8.0,
        shake_dwell_ms=130,
        look_left_offset_deg=-18.0,
        look_right_offset_deg=18.0,
        look_dwell_ms=320,
        wake_up_tilt_offset_deg=6.0,
        wake_up_dwell_ms=220,
    ):
        self.head = head
        self.arms = arms
        self.default_repeat_count = max(1, int(default_repeat_count))
        self.max_repeat_count = max(1, int(max_repeat_count))
        self.target_tolerance_deg = max(0.1, float(target_tolerance_deg))

        self.nod_up_offset_deg = float(nod_up_offset_deg)
        self.nod_down_offset_deg = float(nod_down_offset_deg)
        self.nod_dwell_ms = max(0, int(nod_dwell_ms))

        self.shake_left_offset_deg = float(shake_left_offset_deg)
        self.shake_right_offset_deg = float(shake_right_offset_deg)
        self.shake_dwell_ms = max(0, int(shake_dwell_ms))

        self.look_left_offset_deg = float(look_left_offset_deg)
        self.look_right_offset_deg = float(look_right_offset_deg)
        self.look_dwell_ms = max(0, int(look_dwell_ms))

        self.wake_up_tilt_offset_deg = float(wake_up_tilt_offset_deg)
        self.wake_up_dwell_ms = max(0, int(wake_up_dwell_ms))

        self.active = False
        self.name = None
        self.steps = []
        self.step_index = 0
        self.arrived_ms = None

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
        return (axis, float(value), max(0, int(dwell_ms)))

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

    def start(self, name, count=None):
        name = str(name).strip().upper()
        if name not in self.VALID_GESTURES:
            print("Unsupported gesture:", name)
            return False

        repeat_count = self._normalize_count(count)
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
            steps = self._build_shake_steps(
                repeat_count,
                base_pan,
                self.look_dwell_ms,
                self.look_left_offset_deg,
                self.look_right_offset_deg,
            )
        elif name == "SLEEP":
            steps = [
                self._step("POSE", self.head.pan_head_neutral_angle, 0),
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

        self.cancel(hold_position=False)
        self.name = name
        self.steps = steps
        self.step_index = 0
        self.arrived_ms = None
        self.active = bool(steps)

        if name == "CELEBRATE" and self.arms is not None:
            self.arms.start_wave()

        if self.active:
            print("Gesture start: {} x{}".format(name, repeat_count))
            self._apply_current_step()
        return self.active

    def cancel(self, hold_position=True):
        was_active = self.active
        self.active = False
        self.name = None
        self.steps = []
        self.step_index = 0
        self.arrived_ms = None

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
            # For SLEEP, value is the neutral pan; tilt is set in the next step.
            self.head.set_pan(value)

    def _current_step_reached(self):
        axis, _value, _dwell_ms = self.steps[self.step_index]
        if axis == "PAN":
            return self.head.is_pan_at_target(self.target_tolerance_deg)
        if axis == "TILT":
            return self.head.is_tilt_at_target(self.target_tolerance_deg)
        if axis == "POSE":
            return self.head.is_pan_at_target(self.target_tolerance_deg)
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
            print("Gesture complete:", completed_name)
            return False

        self._apply_current_step()
        return True
