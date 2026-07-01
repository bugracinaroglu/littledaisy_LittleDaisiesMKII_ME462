# =====================================================
# General
# =====================================================

LCD_ENABLED = True
TOUCH_ENABLED = True

HEAD_PAN_SERVO_ENABLED = True
HEAD_TILT_SERVO_ENABLED = True
ARM_SERVOS_ENABLED = True

TOUCH_FACE_TEST_ENABLED = True
DEFAULT_FACE = "NEUTRAL"
STARTUP_CONTROL_MODE = "AUTO"

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
# Head pan and tilt servos
# =====================================================

# Existing left-right head servo.
HEAD_PAN_SERVO_PIN = 28

# New up-down head servo. GPIO 20 does not overlap the LCD/touch/IMU pins
# used by rp2350_touch_lcd_128.py, or the existing arm/pan servo pins.
# Change only this value if your physical wiring uses another free GPIO.
HEAD_TILT_SERVO_PIN = 27

# The Raspberry Pi sends the desired HEAD pan angle, centred at 90 degrees.
# The external 1:1.7 gear pair reverses direction, so the RP2350 converts
# head angle to physical servo angle before commanding the pan servo.
HEAD_PAN_HEAD_NEUTRAL_ANGLE = 90.0
HEAD_PAN_COMMAND_MIN_ANGLE = 0.0
HEAD_PAN_COMMAND_MAX_ANGLE = 180.0

HEAD_PAN_SERVO_NEUTRAL_ANGLE = 90.0
HEAD_PAN_MIN_LIMIT_ANGLE = 0.0
HEAD_PAN_MAX_LIMIT_ANGLE = 180.0
HEAD_PAN_GEAR_RATIO = 1.7
HEAD_PAN_GEAR_REVERSES_DIRECTION = False

HEAD_PAN_STEP_DEG = 3.0
HEAD_PAN_MOVE_INTERVAL_MS = 5

# Tilt is directly driven: incoming HEAD_TILT / HEAD_POSE tilt values are
# physical servo angles and are clamped to the measured safe range.
HEAD_TILT_NEUTRAL_ANGLE = 40.0
HEAD_TILT_MIN_LIMIT_ANGLE = 25.0
HEAD_TILT_MAX_LIMIT_ANGLE = 60.0
HEAD_TILT_STEP_DEG = 2.0
HEAD_TILT_MOVE_INTERVAL_MS = 7

# Backward-compatible alias for any older helper code.
HEAD_PAN_NEUTRAL_ANGLE = HEAD_PAN_SERVO_NEUTRAL_ANGLE

# =====================================================
# Arm servos
# =====================================================

LEFT_ARM_SERVO_PIN = 16
RIGHT_ARM_SERVO_PIN = 17

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
RUNNING_DELTA_MAG_THRESHOLD = 0.22
RUNNING_DELTA_MAG_STRONG_THRESHOLD = 0.90
RUNNING_START_COUNT = 3
RUNNING_STOP_COUNT = 6
RUNNING_ARM_MIN_ACTIVE_MS = 200
RUNNING_FACE_MIN_ACTIVE_MS = 300

RUNNING_ARM_AMPLITUDE_DEG = 30
RUNNING_ARM_INTERVAL_MS = 100
RUNNING_USE_RIGHT_ARM = True

RUNNING_FACE_DIRECTION_SCALE = 2.5
RUNNING_FACE_REVERSE_X = False
RUNNING_FACE_REVERSE_Y = False
RUNNING_FACE_SWAP_XY = False

DIZZY_GYRO_THRESHOLD_DPS = 420.0
DIZZY_FACE_DURATION_MS = 4500
