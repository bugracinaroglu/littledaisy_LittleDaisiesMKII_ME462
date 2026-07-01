from time import ticks_ms, ticks_diff, ticks_add
import math

from rp2350_touch_lcd_128 import QMI8658


def clamp(value, low, high):
    return max(low, min(value, high))


class IMUMotionDetector:
    def __init__(
        self,
        enabled=True,
        sample_interval_ms=20,
        startup_ignore_ms=500,

        delta_mag_threshold=0.35,
        delta_mag_strong_threshold=0.90,

        start_count_required=4,
        stop_count_required=10,

        direction_scale=2.5,
        reverse_x=False,
        reverse_y=False,
        swap_xy=False,

        dizzy_gyro_threshold_dps=420.0,
        dizzy_face_duration_ms=4500
    ):
        self.enabled = enabled
        self.sample_interval_ms = sample_interval_ms
        self.startup_ignore_ms = startup_ignore_ms

        self.delta_mag_threshold = delta_mag_threshold
        self.delta_mag_strong_threshold = delta_mag_strong_threshold

        self.start_count_required = start_count_required
        self.stop_count_required = stop_count_required

        self.direction_scale = direction_scale
        self.reverse_x = reverse_x
        self.reverse_y = reverse_y
        self.swap_xy = swap_xy

        self.dizzy_gyro_threshold_dps = dizzy_gyro_threshold_dps
        self.dizzy_face_duration_ms = dizzy_face_duration_ms

        self.imu = None

        self.start_time_ms = ticks_ms()
        self.last_sample_ms = ticks_ms()

        self.last_acc = None
        self.last_acc_mag = None

        self.running_active = False
        self.running_started_ms = ticks_ms()

        self.start_count = 0
        self.stop_count = 0

        self.filtered_screen_x = 0.0
        self.filtered_screen_y = 0.0
        self.direction_alpha = 0.60

        self.dizzy_until_ms = ticks_ms()

        self.last_result = self._empty_result()

        if self.enabled:
            self._init_imu()

    # =====================================================
    # Init / result helpers
    # =====================================================

    def _init_imu(self):
        try:
            self.imu = QMI8658()
            print("IMU initialized.")
            print("Reactive delta-magnitude running detector active.")

        except Exception as e:
            print("IMU init error:", e)
            self.imu = None
            self.enabled = False

    def _empty_result(self):
        return {
            "ok": False,
            "imu_ready": False,

            "acc": (0.0, 0.0, 0.0),
            "gyro": (0.0, 0.0, 0.0),

            "acc_mag": 0.0,
            "delta_mag": 0.0,

            "moving_candidate": False,
            "strong_candidate": False,

            "start_count": 0,
            "stop_count": 0,

            "running_active": False,
            "running_elapsed_ms": 0,

            "screen_x": 0.0,
            "screen_y": 0.0,

            "dizzy_active": False,
            "gyro_max_abs": 0.0,
        }

    # =====================================================
    # Math helpers
    # =====================================================

    def _vector_mag(self, v):
        return math.sqrt(
            v[0] * v[0] +
            v[1] * v[1] +
            v[2] * v[2]
        )

    # =====================================================
    # Running detection
    # =====================================================

    def _update_running_state(self, delta_mag, imu_ready):
        if not imu_ready:
            self.running_active = False
            self.start_count = 0
            self.stop_count = 0
            return False, False

        moving_candidate = delta_mag >= self.delta_mag_threshold
        strong_candidate = delta_mag >= self.delta_mag_strong_threshold

        if strong_candidate:
            # Strong movement should start faster.
            self.start_count += 2
            self.stop_count = 0

        elif moving_candidate:
            self.start_count += 1
            self.stop_count = 0

        else:
            self.stop_count += 1
            self.start_count = 0

        if not self.running_active:
            if self.start_count >= self.start_count_required:
                self.running_active = True
                self.running_started_ms = ticks_ms()
                print("IMU RUNNING ACTIVE")

        else:
            if self.stop_count >= self.stop_count_required:
                self.running_active = False
                print("IMU RUNNING STOP")

        return moving_candidate, strong_candidate

    # =====================================================
    # Direction mapping for running face
    # =====================================================

    def _screen_direction_from_acc_delta(self, acc, last_acc):
        if last_acc is None:
            return 0.0, 0.0

        dx = acc[0] - last_acc[0]
        dy = acc[1] - last_acc[1]

        # IMU axes:
        # +X -> screen top
        # +Y -> screen right
        #
        # LCD pixel axes:
        # screen_x positive -> right
        # screen_y positive -> down
        screen_x = dy
        screen_y = -dx

        if self.swap_xy:
            screen_x, screen_y = screen_y, screen_x

        if self.reverse_x:
            screen_x *= -1.0

        if self.reverse_y:
            screen_y *= -1.0

        screen_x = clamp(screen_x / self.direction_scale, -1.0, 1.0)
        screen_y = clamp(screen_y / self.direction_scale, -1.0, 1.0)

        self.filtered_screen_x = (
            self.direction_alpha * self.filtered_screen_x +
            (1.0 - self.direction_alpha) * screen_x
        )

        self.filtered_screen_y = (
            self.direction_alpha * self.filtered_screen_y +
            (1.0 - self.direction_alpha) * screen_y
        )

        return self.filtered_screen_x, self.filtered_screen_y

    # =====================================================
    # Dizzy detection
    # =====================================================

    def _update_dizzy_state(self, now, gyro):
        gyro_max_abs = max(
            abs(gyro[0]),
            abs(gyro[1]),
            abs(gyro[2])
        )

        if gyro_max_abs >= self.dizzy_gyro_threshold_dps:
            self.dizzy_until_ms = ticks_add(now, self.dizzy_face_duration_ms)
            print("IMU DIZZY TRIGGER:", gyro_max_abs)

        dizzy_active = ticks_diff(self.dizzy_until_ms, now) > 0

        return dizzy_active, gyro_max_abs

    # =====================================================
    # Main update
    # =====================================================

    def update(self):
        if not self.enabled or self.imu is None:
            return self.last_result

        now = ticks_ms()

        if ticks_diff(now, self.last_sample_ms) < self.sample_interval_ms:
            return self.last_result

        self.last_sample_ms = now

        try:
            xyz = self.imu.Read_XYZ()

        except Exception as e:
            print("IMU read error:", e)
            self.last_result = self._empty_result()
            return self.last_result

        acc = (
            float(xyz[0]),
            float(xyz[1]),
            float(xyz[2])
        )

        gyro = (
            float(xyz[3]),
            float(xyz[4]),
            float(xyz[5])
        )

        acc_mag = self._vector_mag(acc)

        if self.last_acc_mag is None:
            delta_mag = 0.0
        else:
            delta_mag = abs(acc_mag - self.last_acc_mag)

        startup_elapsed_ms = ticks_diff(now, self.start_time_ms)

        imu_ready = (
            startup_elapsed_ms >= self.startup_ignore_ms and
            self.last_acc_mag is not None
        )

        moving_candidate, strong_candidate = self._update_running_state(
            delta_mag,
            imu_ready
        )

        if self.running_active:
            running_elapsed_ms = ticks_diff(now, self.running_started_ms)
        else:
            running_elapsed_ms = 0

        screen_x, screen_y = self._screen_direction_from_acc_delta(
            acc,
            self.last_acc
        )

        dizzy_active, gyro_max_abs = self._update_dizzy_state(now, gyro)

        self.last_result = {
            "ok": True,
            "imu_ready": imu_ready,

            "acc": acc,
            "gyro": gyro,

            "acc_mag": acc_mag,
            "delta_mag": delta_mag,

            "moving_candidate": moving_candidate,
            "strong_candidate": strong_candidate,

            "start_count": self.start_count,
            "stop_count": self.stop_count,

            "running_active": self.running_active,
            "running_elapsed_ms": running_elapsed_ms,

            "screen_x": screen_x,
            "screen_y": screen_y,

            "dizzy_active": dizzy_active,
            "gyro_max_abs": gyro_max_abs,
        }

        self.last_acc = acc
        self.last_acc_mag = acc_mag

        return self.last_result