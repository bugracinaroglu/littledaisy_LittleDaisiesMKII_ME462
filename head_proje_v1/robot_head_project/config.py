# =====================================================
# Camera
# =====================================================

CAMERA_INDEX = 0

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

FLIP_FRAME_HORIZONTAL = True
FLIP_FRAME_VERTICAL = False

CAMERA_HORIZONTAL_FOV_DEG = 95.0

WINDOW_NAME = "Robot Head PC Controller"


# =====================================================
# Camera Mount Mode
# =====================================================

# Options:
# "fixed"        -> camera is stationary, head rotates separately
# "head_mounted" -> camera rotates with the head
CAMERA_MOUNT_MODE = "fixed"


# =====================================================
# Feature Flags
# =====================================================

ENABLE_HEAD_TRACKING = True
ENABLE_ARM_WAVE = True
ENABLE_LCD_FACE = True

HEAD_SERVO_ENABLED = True
ARM_SERVOS_ENABLED = True
LCD_ENABLED = True

ENABLE_HUMAN_TRACKING = True
ENABLE_EMOTION = True
ENABLE_GESTURE = True

ENABLE_SERIAL = False


# =====================================================
# Serial
# =====================================================

SERIAL_PORT = "auto"
BAUDRATE = 115200


# =====================================================
# Human Tracking
# =====================================================

POSE_DETECTION_CONFIDENCE = 0.60
POSE_TRACKING_CONFIDENCE = 0.60


# =====================================================
# Emotion Detection
# =====================================================

EMOTION_ANALYZE_EVERY_N_FRAMES = 10
EMOTION_DETECTOR_BACKEND = "opencv"
EMOTION_ENFORCE_DETECTION = True


# =====================================================
# Gesture Detection
# =====================================================

MAX_NUM_HANDS = 2

GESTURE_PROCESS_EVERY_N_FRAMES = 1
HAND_DETECTION_CONFIDENCE = 0.60
HAND_TRACKING_CONFIDENCE = 0.60

WAVE_HISTORY_SIZE = 20
WAVE_MIN_X_RANGE = 0.12
WAVE_MIN_DIRECTION_CHANGES = 1
WAVE_MIN_STEP = 0.01
HELLO_COOLDOWN_FRAMES = 30


# =====================================================
# Head Servo
# =====================================================

HEAD_SERVO_CENTER_ANGLE = 90.0
HEAD_SERVO_MIN_ANGLE = 0.0
HEAD_SERVO_MAX_ANGLE = 180.0

# Extra soft limit around center for safety.
HEAD_SERVO_SOFT_LIMIT_FROM_CENTER_DEG = 55.0

# If servo moves opposite direction, set -1.
HEAD_SERVO_DIRECTION = 1

# If visual output is correct but servo control is reversed, use this.
REVERSE_X_OUTPUT = False

# If tilt servo is added later.
REVERSE_Y_OUTPUT = False


# =====================================================
# Smooth Tracking
# =====================================================

DEADBAND_PIXELS = 50
DEADBAND_NORM = 0.04

ERROR_SMOOTHING_ALPHA = 0.75

SEND_INTERVAL_SEC = 0.08
MIN_ANGLE_CHANGE_TO_SEND = 0.7
MAX_TARGET_STEP_PER_SEND = 2.0


# =====================================================
# Face / LCD
# =====================================================

DEFAULT_FACE = "CURIOUS"
NO_HUMAN_FACE = "SLEEPING"

SUPPORTED_FACES = [
    "NEUTRAL",
    "CURIOUS",
    "HAPPY",
    "SAD",
    "ANGRY",
    "SURPRISED",
    "SLEEPING",
    "IDLE"
]