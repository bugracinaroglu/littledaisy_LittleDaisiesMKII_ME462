class ControlMode:
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    ROS = "ROS"

    ALL = (AUTO, MANUAL, ROS)

    @classmethod
    def normalize(cls, mode):
        normalized = str(mode).strip().upper()
        if normalized not in cls.ALL:
            raise ValueError(
                "Unsupported control mode: {}. Expected one of {}".format(
                    mode,
                    ", ".join(cls.ALL),
                )
            )
        return normalized


class ControlModeManager:
    """Owns the single active command authority for the robot head."""

    def __init__(self, initial_mode=ControlMode.AUTO):
        self._mode = ControlMode.normalize(initial_mode)
        self._listeners = []

    def get_mode(self):
        return self._mode

    def is_mode(self, mode):
        return self._mode == ControlMode.normalize(mode)

    def can_execute(self, source):
        return self._mode == ControlMode.normalize(source)

    def add_listener(self, listener):
        if listener is not None and listener not in self._listeners:
            self._listeners.append(listener)

    def set_mode(self, mode):
        new_mode = ControlMode.normalize(mode)
        if new_mode == self._mode:
            return False

        old_mode = self._mode
        self._mode = new_mode
        print("[Control mode]: {} -> {}".format(old_mode, new_mode))

        for listener in tuple(self._listeners):
            try:
                listener(old_mode, new_mode)
            except Exception as exc:
                print("Control-mode listener error:", exc)

        return True
