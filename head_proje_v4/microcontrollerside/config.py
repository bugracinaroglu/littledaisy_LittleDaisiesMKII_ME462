# =====================================================
# General
# =====================================================

LCD_ENABLED = True
TOUCH_ENABLED = True

HEAD_SERVO_ENABLED = True
ARM_SERVOS_ENABLED = True

TOUCH_FACE_TEST_ENABLED = True

DEFAULT_FACE = "NEUTRAL"


# =====================================================
# Supported faces
# =====================================================

FACE_LIST = [
    "NEUTRAL",
    "CURIOUS",
    "HAPPY",
    "SAD",
    "ANGRY",
    "SURPRISED",
    "DISGUST",
    "SLEEPING",
    "IDLE",
    "RUNNING",
    "DIZZY",
]


# =====================================================
# Servo common settings
# =====================================================

SERVO_FREQ = 50
SERVO_MIN_US = 500
SERVO_MAX_US = 2500
SERVO_MAX_ANGLE = 180


# =====================================================
# Head servo
# =====================================================

HEAD_SERVO_PIN = 28

HEAD_NEUTRAL_ANGLE = 90
HEAD_MIN_LIMIT_ANGLE = 0
HEAD_MAX_LIMIT_ANGLE = 180

HEAD_STEP_DEG = 3.0
HEAD_MOVE_INTERVAL_MS = 5


# =====================================================
# Arm servos
# =====================================================

LEFT_ARM_SERVO_PIN = 26
RIGHT_ARM_SERVO_PIN = 27

LEFT_ARM_NEUTRAL_ANGLE = 90
RIGHT_ARM_NEUTRAL_ANGLE = 90

LEFT_ARM_UP_ANGLE = 50
RIGHT_ARM_UP_ANGLE = 130

LEFT_ARM_MIN_LIMIT_ANGLE = 20
LEFT_ARM_MAX_LIMIT_ANGLE = 160

RIGHT_ARM_MIN_LIMIT_ANGLE = 20
RIGHT_ARM_MAX_LIMIT_ANGLE = 160

ARM_STEP_DEG = 3
ARM_MOVE_INTERVAL_MS = 12

ARM_WAVE_AMPLITUDE_DEG = 40
ARM_WAVE_INTERVAL_MS = 180
ARM_WAVE_CYCLES = 4

# Şimdilik sadece sol kol selam versin.
USE_RIGHT_ARM_FOR_WAVE = False


# =====================================================
# IMU / Running Motion
# =====================================================

IMU_ENABLED = True

RUNNING_ARM_ENABLE = True
RUNNING_FACE_ENABLE = True
DIZZY_FACE_ENABLE = True

IMU_SAMPLE_INTERVAL_MS = 20
IMU_STARTUP_IGNORE_MS = 500

# New reactive running detection:
# acc_mag = sqrt(ax^2 + ay^2 + az^2)
# delta_mag = abs(acc_mag_now - acc_mag_previous)
RUNNING_DELTA_MAG_THRESHOLD = 0.22
RUNNING_DELTA_MAG_STRONG_THRESHOLD = 0.90

# 20 ms sample interval:
# 4 samples ≈ 80 ms start confirmation
# 10 samples ≈ 200 ms stop confirmation
RUNNING_START_COUNT = 3
RUNNING_STOP_COUNT = 6

# Daha reaktif olması için küçük tuttuk
RUNNING_ARM_MIN_ACTIVE_MS = 200
RUNNING_FACE_MIN_ACTIVE_MS = 300

# Running arm motion
RUNNING_ARM_AMPLITUDE_DEG = 30
RUNNING_ARM_INTERVAL_MS = 100
RUNNING_USE_RIGHT_ARM = True

# Running face direction
RUNNING_FACE_DIRECTION_SCALE = 2.5
RUNNING_FACE_REVERSE_X = False
RUNNING_FACE_REVERSE_Y = False
RUNNING_FACE_SWAP_XY = False

# Dizzy
DIZZY_GYRO_THRESHOLD_DPS = 420.0
DIZZY_FACE_DURATION_MS = 4500