import time
import glob

try:
    import serial
except ImportError:
    serial = None


class CommandSender:
    def __init__(
        self,
        enable_serial=False,
        serial_port="auto",
        baudrate=115200,
        send_interval_sec=0.08,
        min_angle_change_to_send=0.7
    ):
        self.enable_serial = enable_serial
        self.serial_port = serial_port
        self.baudrate = baudrate

        self.send_interval_sec = send_interval_sec
        self.min_angle_change_to_send = min_angle_change_to_send

        self.ser = None

        self.last_send_time = 0.0
        self.last_head_angle_sent = None

        if self.enable_serial:
            self.ser = self._open_serial_connection()

    def _auto_find_serial_port(self):
        candidates = []
        candidates.extend(glob.glob("/dev/ttyACM*"))
        candidates.extend(glob.glob("/dev/ttyUSB*"))

        if len(candidates) == 0:
            return None

        return candidates[0]

    def _open_serial_connection(self):
        if serial is None:
            print("pyserial is not installed. Serial disabled.")
            return None

        port = self.serial_port

        if port == "auto":
            port = self._auto_find_serial_port()

        if port is None:
            print("RP2350 serial port not found. Running vision only.")
            return None

        try:
            ser = serial.Serial(port, self.baudrate, timeout=0)
            time.sleep(2.0)
            ser.reset_input_buffer()
            print("Connected to RP2350:", port)
            return ser

        except Exception as e:
            print("Could not open serial port:", e)
            return None

    def is_connected(self):
        return self.ser is not None

    def send_raw(self, cmd):
        if not self.enable_serial or self.ser is None:
            return False

        try:
            self.ser.write((cmd + "\n").encode("utf-8"))
            return True

        except Exception as e:
            print("Serial send error:", e)
            return False

    def send_head_angle(self, angle):
        now = time.monotonic()

        if self.last_head_angle_sent is not None:
            angle_change = abs(angle - self.last_head_angle_sent)
        else:
            angle_change = 999.0

        should_send = (
            now - self.last_send_time >= self.send_interval_sec and
            angle_change >= self.min_angle_change_to_send
        )

        if not should_send:
            return False

        cmd = f"HEAD:{angle:.1f}"
        sent = self.send_raw(cmd)

        if sent:
            self.last_head_angle_sent = angle
            self.last_send_time = now
            print("Sent:", cmd)

        return sent

    def send_face(self, face_name):
        return self.send_raw(f"FACE:{face_name}")

    def send_arm_wave(self):
        return self.send_raw("ARM:WAVE")

    def send_center(self):
        return self.send_raw("CENTER")

    def send_stop(self):
        return self.send_raw("STOP")

    def close(self):
        if self.ser is not None:
            self.ser.close()