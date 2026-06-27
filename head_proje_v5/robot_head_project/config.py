# =====================================================
# Camera
# =====================================================

# Options:
#   "opencv"    -> USB webcam
#   "picamera2" -> Raspberry Pi ribbon camera
CAMERA_BACKEND = "picamera2"

# Options:
#   "usb_webcam"
#   "pi_v2"
#   "pi_fisheye"
CAMERA_PROFILE = "pi_fisheye"

CAMERA_INDEX = 0

FRAME_WIDTH = 1296
FRAME_HEIGHT = 972

FLIP_FRAME_HORIZONTAL = True
FLIP_FRAME_VERTICAL = False

# Fixed camera servo mapping için önemli.
# Fisheye için bunu deneyerek ayarlayacağız.
CAMERA_HORIZONTAL_FOV_DEG = 120.0

WINDOW_NAME = "Robot Head PC Controller"


# =====================================================
# Fisheye / Distortion Correction
# =====================================================

# Options:
#   "none"       -> no correction
#   "crop"       -> center crop
#   "defish"     -> manual fisheye correction, no calibration needed
#   "calibrated" -> needs real camera calibration values
FISHEYE_CORRECTION_MODE = "defish"

# Crop mode için
FISHEYE_CROP_SCALE = 0.75

# Manual defish mode için
# Senin kameranın diagonal angle of view değeri 200 derece.
DEFISH_INPUT_DIAGONAL_FOV_DEG = 200.0

# 200 dereceyi tamamen rectilinear yapamayız.
# 145-170 arası dene.
# Büyük değer -> daha geniş görüntü, daha fazla kenar esnemesi
# Küçük değer -> daha düzgün görüntü, daha dar görüş
DEFISH_OUTPUT_DIAGONAL_FOV_DEG = 165.0

# 0.0 -> correction yok
# 1.0 -> full defish
# 0.45-0.75 arası genelde daha doğal olur.
DEFISH_STRENGTH = 0.15

# 1.0 normal.
# Daha küçük -> biraz daha geniş görünür
# Daha büyük -> biraz zoom yapar
DEFISH_ZOOM = 1.0


# Calibrated mode için şimdilik boş kalsın
FISHEYE_CAMERA_MATRIX = None
FISHEYE_DIST_COEFFS = None
FISHEYE_BALANCE = 1.0
# =====================================================
# Camera Mount Mode
# =====================================================

CAMERA_MOUNT_MODE = "head_mounted"        # "fixed" or "head_mounted"


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
ENABLE_EMOTION = False
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

HEAD_SERVO_SOFT_LIMIT_FROM_CENTER_DEG = 45.0

HEAD_SERVO_DIRECTION = 1
CONTROL_REVERSE_X = False


# =====================================================
# Smooth Tracking
# =====================================================

DEADBAND_PIXELS = 50
DEADBAND_NORM = 0.045

ERROR_SMOOTHING_ALPHA = 0.5

SEND_INTERVAL_SEC = 0.02 #0.02
MIN_ANGLE_CHANGE_TO_SEND = 0.8 #0.8
MAX_TARGET_STEP_PER_SEND = 2.5 #2.5


# =====================================================
# Head-mounted Directional Control
# =====================================================

HEAD_MOUNTED_GAIN = 20
HEAD_MOUNTED_MIN_STEP_DEG = 0.30
HEAD_MOUNTED_MAX_STEP_DEG = 2.30


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