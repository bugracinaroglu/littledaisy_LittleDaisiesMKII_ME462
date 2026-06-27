import sys

try:
    import uselect as select
except ImportError:
    import select


class SerialParser:
    def __init__(self):
        pass

    def read_command(self):
        try:
            if select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline()

                if line is None:
                    return None

                line = line.strip()

                if line == "":
                    return None

                return line

        except Exception as e:
            print("Serial read error:", e)

        return None

    def parse(self, cmd):
        if cmd is None:
            return None, None

        cmd = cmd.strip()

        if cmd == "":
            return None, None

        upper = cmd.upper()

        # Compatibility with old code: A:90
        if upper.startswith("A:"):
            try:
                return "HEAD", float(cmd[2:])
            except:
                return "ERROR", cmd

        if upper.startswith("HEAD:"):
            try:
                return "HEAD", float(cmd[5:])
            except:
                return "ERROR", cmd

        if upper.startswith("FACE:"):
            face_name = cmd[5:].strip().upper()
            return "FACE", face_name

        if upper.startswith("ARM:"):
            arm_cmd = cmd[4:].strip().upper()

            if arm_cmd == "WAVE":
                return "ARM_WAVE", None

            return "ARM", arm_cmd

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

        # Direct face command shortcut:
        # HAPPY, SAD, ANGRY, etc.
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