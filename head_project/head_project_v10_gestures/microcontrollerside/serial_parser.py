import sys

try:
    import uselect as select
except ImportError:
    import select


class SerialParser:
    def read_command(self):
        try:
            if select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline()
                if line is None:
                    return None
                line = line.strip()
                return line if line else None
        except Exception as exc:
            print("Serial read error:", exc)
        return None

    @staticmethod
    def _parse_nonnegative_int(value, original_command):
        try:
            parsed = int(value)
            if parsed < 0:
                raise ValueError
            return parsed
        except Exception:
            return "ERROR", original_command

    def _parse_face(self, payload, original_command):
        parts = [part.strip() for part in payload.split(",")]
        if len(parts) not in (1, 2) or not parts[0]:
            return "ERROR", original_command

        face_name = parts[0].upper()
        hold_ms = 0
        if len(parts) == 2:
            parsed = self._parse_nonnegative_int(parts[1], original_command)
            if isinstance(parsed, tuple):
                return parsed
            hold_ms = parsed

        return "FACE", (face_name, hold_ms)

    def _parse_gesture(self, payload, original_command):
        parts = [part.strip() for part in payload.split(",")]
        if len(parts) < 1 or len(parts) > 3 or not parts[0]:
            return "ERROR", original_command

        gesture_name = parts[0].upper()
        if gesture_name == "CANCEL":
            return "GESTURE_CANCEL", None

        count = 0
        hold_ms = 0

        if len(parts) >= 2 and parts[1]:
            parsed = self._parse_nonnegative_int(parts[1], original_command)
            if isinstance(parsed, tuple):
                return parsed
            count = parsed

        if len(parts) >= 3 and parts[2]:
            parsed = self._parse_nonnegative_int(parts[2], original_command)
            if isinstance(parsed, tuple):
                return parsed
            hold_ms = parsed

        return "GESTURE", (gesture_name, count, hold_ms)

    def parse(self, cmd):
        if cmd is None:
            return None, None

        cmd = cmd.strip()
        if not cmd:
            return None, None

        upper = cmd.upper()

        if upper.startswith("HEAD_POSE:"):
            payload = cmd[len("HEAD_POSE:"):]
            parts = payload.split(",")
            if len(parts) != 2:
                return "ERROR", cmd
            try:
                return "HEAD_POSE", (float(parts[0]), float(parts[1]))
            except Exception:
                return "ERROR", cmd

        if upper.startswith("HEAD_PAN:"):
            try:
                return "HEAD_PAN", float(cmd[len("HEAD_PAN:"):])
            except Exception:
                return "ERROR", cmd

        if upper.startswith("HEAD_TILT:"):
            try:
                return "HEAD_TILT", float(cmd[len("HEAD_TILT:"):])
            except Exception:
                return "ERROR", cmd

        # Manual backwards compatibility: HEAD:90 and A:90 control pan only.
        if upper.startswith("HEAD:"):
            try:
                return "HEAD_PAN", float(cmd[len("HEAD:"):])
            except Exception:
                return "ERROR", cmd

        if upper.startswith("A:"):
            try:
                return "HEAD_PAN", float(cmd[2:])
            except Exception:
                return "ERROR", cmd

        if upper.startswith("FACE:"):
            return self._parse_face(cmd[5:].strip(), cmd)

        if upper.startswith("GESTURE:"):
            return self._parse_gesture(cmd[len("GESTURE:"):].strip(), cmd)

        # Alias retained for future callers that describe only a head action.
        if upper.startswith("HEAD_ACTION:"):
            return self._parse_gesture(cmd[len("HEAD_ACTION:"):].strip(), cmd)

        if upper.startswith("MODE:"):
            return "MODE", cmd[5:].strip().upper()

        if upper.startswith("ARM:"):
            arm_command = cmd[4:].strip().upper()
            if arm_command == "WAVE":
                return "ARM_WAVE", None
            return "ARM", arm_command

        if upper in ("AUTO", "MANUAL", "ROS"):
            return "MODE", upper

        if upper in ("CENTER", "HOME"):
            return "CENTER", None
        if upper == "STOP":
            return "STOP", None

        direct_gestures = (
            "NOD",
            "SUNGLASSES_NOD",
            "SIGMA_NOD",
            "SHAKE",
            "LOOK_AROUND",
            "CELEBRATE",
            "WAKE_UP",
        )
        if upper in direct_gestures:
            return "GESTURE", (upper, 0, 0)
        if upper in ("CANCEL_GESTURE", "GESTURE_CANCEL"):
            return "GESTURE_CANCEL", None
        if upper == "SLEEP":
            return "GESTURE", ("SLEEP", 1, 0)
        if upper == "WAKE":
            return "GESTURE", ("WAKE_UP", 1, 0)

        direct_faces = (
            "NEUTRAL",
            "CURIOUS",
            "HAPPY",
            "SAD",
            "ANGRY",
            "SURPRISED",
            "DISGUST",
            "SLEEPING",
            "IDLE",
            "SIGMA",
            "SUNGLASSES",
        )
        if upper in direct_faces:
            return "FACE", (upper, 0)

        return "UNKNOWN", cmd
