# =====================================================
# General
# =====================================================

LCD_ENABLED = True
TOUCH_ENABLED = True

HEAD_SERVO_ENABLED = True
ARM_SERVOS_ENABLED = True

# Touch ile yüzleri test etmek istersen True yap.
# Final robotta False kalabilir.
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

# Şimdilik sadece sol kol sallasın.
USE_RIGHT_ARM_FOR_WAVE = True