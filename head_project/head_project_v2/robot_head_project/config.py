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

CAMERA_MOUNT_MODE = "fixed"        # "fixed" or "head_mounted"


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

ENABLE_SERIAL = True


# =====================================================
# Serial
# =====================================================

SERIAL_PORT = "auto"
# SERIAL_PORT = "/dev/ttyACM0"
BAUDRATE = 115200


# =====================================================
# Human Tracking
# =====================================================

POSE_DETECTION_CONFIDENCE = 0.70
POSE_TRACKING_CONFIDENCE = 0.70

ENABLE_FACE_FALLBACK = True

# Do not require hips all the time.
# If full torso is not visible, upper body will be used.
STRICT_TORSO_VALIDATION = False

MIN_BODY_HEIGHT_RATIO = 0.16
MIN_BODY_WIDTH_RATIO = 0.08

MIN_UPPER_BODY_HEIGHT_RATIO = 0.10
MIN_UPPER_BODY_WIDTH_RATIO = 0.08

MIN_VISIBLE_POSE_POINTS = 5


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

# Wave detection
WAVE_HISTORY_SIZE = 20
WAVE_MIN_X_RANGE = 0.08
WAVE_MIN_DIRECTION_CHANGES = 1
WAVE_MIN_STEP = 0.008

# Open palm detection
OPEN_PALM_ENABLED = True
OPEN_PALM_MIN_FINGERS = 5
OPEN_PALM_HOLD_FRAMES = 30

HELLO_COOLDOWN_FRAMES = 30


# =====================================================
# Head Servo
# =====================================================

HEAD_SERVO_CENTER_ANGLE = 90.0
HEAD_SERVO_MIN_ANGLE = 0.0
HEAD_SERVO_MAX_ANGLE = 180.0

HEAD_SERVO_SOFT_LIMIT_FROM_CENTER_DEG = 55.0

# If servo moves opposite direction, change this to -1.
HEAD_SERVO_DIRECTION = 1

# Controller-side reverse.
# This reverses the x error before angle mapping.
CONTROL_REVERSE_X = False


# =====================================================
# Smooth Tracking
# =====================================================

DEADBAND_PIXELS = 50
DEADBAND_NORM = 0.04

ERROR_SMOOTHING_ALPHA = 0.75

SEND_INTERVAL_SEC = 0.02
MIN_ANGLE_CHANGE_TO_SEND = 0.5
MAX_TARGET_STEP_PER_SEND = 4.0


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