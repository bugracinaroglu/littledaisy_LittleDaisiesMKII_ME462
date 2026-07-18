import glob
import threading
import time
import base64

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
        send_interval_sec=0.02,
        min_pan_change_to_send_deg=0.7,
        min_tilt_change_to_send_deg=0.7,
    ):
        self.enable_serial = enable_serial
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.send_interval_sec = float(send_interval_sec)
        self.min_pan_change_to_send_deg = float(
            min_pan_change_to_send_deg
        )
        self.min_tilt_change_to_send_deg = float(
            min_tilt_change_to_send_deg
        )

        self.ser = None
        self._serial_lock = threading.RLock()
        self.last_head_send_time = 0.0
        self.last_pan_angle_sent = None
        self.last_tilt_angle_sent = None

        if self.enable_serial:
            self.ser = self._open_serial_connection()

    @staticmethod
    def _auto_find_serial_port():
        candidates = []
        candidates.extend(sorted(glob.glob("/dev/ttyACM*")))
        candidates.extend(sorted(glob.glob("/dev/ttyUSB*")))
        return candidates[0] if candidates else None

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
            connection = serial.Serial(port, self.baudrate, timeout=0.1)
            time.sleep(2.0)
            connection.reset_input_buffer()
            print("Connected to RP2350:", port)
            
            # Start background thread to print RP2350 logs to PC terminal
            self._reader_thread = threading.Thread(target=self._read_from_serial, args=(connection,), daemon=True)
            self._reader_thread.start()
            
            return connection
        except Exception as exc:
            print("Could not open serial port:", exc)
            return None

    def _read_from_serial(self, connection):
        """Continuously read lines from the RP2350 and print them."""
        while self.enable_serial and connection is not None:
            try:
                if connection.in_waiting > 0:
                    line = connection.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"[RP2350] {line}")
                else:
                    time.sleep(0.01)
            except Exception:
                break

    def is_connected(self):
        return self.ser is not None

    def send_raw(self, command):
        with self._serial_lock:
            if not self.enable_serial or self.ser is None:
                return False

            try:
                self.ser.write((command + "\n").encode("utf-8"))
                return True
            except Exception as exc:
                print("Serial send error:", exc)
                return False

    def send_head_pose(self, pan_angle, tilt_angle, force=False):
        now = time.monotonic()
        pan_change = (
            999.0
            if self.last_pan_angle_sent is None
            else abs(pan_angle - self.last_pan_angle_sent)
        )
        tilt_change = (
            999.0
            if self.last_tilt_angle_sent is None
            else abs(tilt_angle - self.last_tilt_angle_sent)
        )

        interval_ready = (
            now - self.last_head_send_time >= self.send_interval_sec
        )
        meaningful_change = (
            pan_change >= self.min_pan_change_to_send_deg
            or tilt_change >= self.min_tilt_change_to_send_deg
        )
        if not force and (not interval_ready or not meaningful_change):
            return False

        command = "HEAD_POSE:{:.1f},{:.1f}".format(
            pan_angle, tilt_angle
        )
        sent = self.send_raw(command)
        if sent:
            self.last_pan_angle_sent = pan_angle
            self.last_tilt_angle_sent = tilt_angle
            self.last_head_send_time = now
        return sent

    def send_head_pan(self, pan_angle):
        return self.send_raw("HEAD_PAN:{:.1f}".format(pan_angle))

    def send_head_tilt(self, tilt_angle):
        return self.send_raw("HEAD_TILT:{:.1f}".format(tilt_angle))

    def send_face(self, face_name, hold_ms=0):
        hold_ms = max(0, int(hold_ms))
        if hold_ms > 0:
            return self.send_raw("FACE:{},{}".format(face_name, hold_ms))
        return self.send_raw("FACE:{}".format(face_name))

    def send_text(self, text, hold_ms=4000, italic=False):
        clean = " ".join(
            str(text).replace("\r", " ").replace("\n", " ").split()
        )
        if not clean:
            return False

        # Bound serial/LCD workload while preserving commas in the text field.
        clean = clean[:80]
        hold_ms = max(0, int(hold_ms))
        italic_flag = 1 if italic else 0
        return self.send_raw(
            "TEXT:{},{},{}".format(hold_ms, italic_flag, clean)
        )

    def send_oopsie_daisy(self, hold_ms=5000):
        return self.send_text(
            "Oopsie Daisy",
            hold_ms=hold_ms,
            italic=True,
        )

    def send_gesture(self, gesture_name, count=3, hold_ms=0):
        count = max(1, int(count))
        hold_ms = max(0, int(hold_ms))
        return self.send_raw(
            "GESTURE:{},{},{}".format(
                str(gesture_name).strip().upper(),
                count,
                hold_ms,
            )
        )

    def send_cancel_gesture(self):
        return self.send_raw("GESTURE:CANCEL")

    def send_image(self, b64_string):
        return self.send_raw("IMAGE:{}".format(b64_string))

    def send_image_chunked(self, raw_bytes, is_color=False):
        """Send a large image as Base64 chunks to avoid memory overflow on RP2350."""
        # Send START command with metadata
        color_flag = 1 if is_color else 0
        self.send_raw(f"IMAGE_START:{len(raw_bytes)},{color_flag}")
        time.sleep(0.05)  # Wait for microcontroller to allocate memory
        
        chunk_size = 2048
        for i in range(0, len(raw_bytes), chunk_size):
            chunk = raw_bytes[i:i+chunk_size]
            b64_chunk = base64.b64encode(chunk).decode('utf-8')
            self.send_raw(f"IMAGE_CHUNK:{i},{b64_chunk}")
            time.sleep(0.005)  # Prevent USB CDC ring buffer overflow
            
        # Send END command
        return self.send_raw("IMAGE_END:")

    def send_mode(self, mode_name):
        return self.send_raw("MODE:{}".format(str(mode_name).strip().upper()))

    def send_arm_wave(self):
        return self.send_raw("ARM:WAVE")

    def send_center(self):
        return self.send_raw("CENTER")

    def send_stop(self):
        return self.send_raw("STOP")

    def close(self):
        with self._serial_lock:
            if self.ser is not None:
                self.ser.close()
                self.ser = None
