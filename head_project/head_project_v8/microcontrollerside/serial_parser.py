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
    def _parse_float(value, original_command):
        try:
            return float(value)
        except Exception:
            return "ERROR", original_command

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
            return "FACE", cmd[5:].strip().upper()

        if upper.startswith("ARM:"):
            arm_command = cmd[4:].strip().upper()
            if arm_command == "WAVE":
                return "ARM_WAVE", None
            return "ARM", arm_command

        if upper in ("CENTER", "HOME"):
            return "CENTER", None
        if upper == "STOP":
            return "STOP", None
        if upper == "SLEEP":
            return "FACE", "SLEEPING"
        if upper == "IDLE":
            return "FACE", "IDLE"
        if upper == "WAKE":
            return "FACE", "CURIOUS"

        direct_faces = [
            "NEUTRAL",
            "CURIOUS",
            "HAPPY",
            "SAD",
            "ANGRY",
            "SURPRISED",
            "DISGUST",
            "SLEEPING",
            "IDLE",
        ]
        if upper in direct_faces:
            return "FACE", upper

        return "UNKNOWN", cmd
