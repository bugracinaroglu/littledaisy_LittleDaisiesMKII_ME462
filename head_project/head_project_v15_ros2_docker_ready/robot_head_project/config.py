import os


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return bool(default)
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name, default):
    value = os.getenv(name)
    return int(value) if value is not None and value.strip() else int(default)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =====================================================
# Camera
# =====================================================

# "picamera2" for the Raspberry Pi ribbon camera.
# "opencv" may still be used for a USB webcam during development.
CAMERA_BACKEND = "picamera2"
CAMERA_PROFILE = "pi_fisheye"
CAMERA_INDEX = 0

# The supplied calibration was produced at exactly 1296 x 972.
# This is therefore the highest safe default resolution for this calibration.
FRAME_WIDTH = 1296
FRAME_HEIGHT = 972

FLIP_FRAME_HORIZONTAL = True
FLIP_FRAME_VERTICAL = False
WINDOW_NAME = "Robot Head v6 - Fixed Camera Pan/Tilt"

# =====================================================
# On-screen status panel
# =====================================================

SHOW_STATUS_PANEL = True
STATUS_PANEL_WIDTH = 360

# These mirror the RP2350 pan-gear settings and are used only to show the
# estimated physical pan-servo angle in the on-screen panel. The RP2350 still
# performs the real conversion and remains the source of truth.
STATUS_PAN_SERVO_NEUTRAL_ANGLE = 90.0
STATUS_PAN_SERVO_MIN_ANGLE = 0.0
STATUS_PAN_SERVO_MAX_ANGLE = 180.0
STATUS_PAN_GEAR_RATIO = 1.7
STATUS_PAN_GEAR_REVERSES_DIRECTION = False


# =====================================================
# Calibrated fisheye correction
# =====================================================

FISHEYE_CORRECTION_MODE = "calibrated"  # "calibrated" or "none"
CAMERA_CALIBRATION_FILE = os.path.join(
    BASE_DIR,
    "calibration",
    "calibration.json"
)

# 0.0 gave the straightest useful image during calibration tests.
FISHEYE_BALANCE = 0.0
REQUIRE_CALIBRATION = True

# =====================================================
# Feature flags
# =====================================================

ENABLE_HEAD_TRACKING = True
ENABLE_UP_DOWN_HUMAN_TRACKING = True
ENABLE_ARM_WAVE = False
ENABLE_LCD_FACE = True

HEAD_PAN_SERVO_ENABLED = True
HEAD_TILT_SERVO_ENABLED = True
ARM_SERVOS_ENABLED = False
LCD_ENABLED = True

ENABLE_HUMAN_TRACKING = True
ENABLE_EMOTION = True  
ENABLE_GESTURE = False
ENABLE_SERIAL = True


# =====================================================
# Command authority / control mode
# =====================================================

# AUTO: camera, emotion and gesture behavior sends commands.
# MANUAL: keyboard and direct Python API commands are accepted.
# ROS: commands arriving from the Docker ROS2 bridge are accepted.
STARTUP_CONTROL_MODE = os.getenv("ROBOT_HEAD_STARTUP_MODE", "AUTO").strip().upper()

# Optional in-process rclpy bridge. Leave disabled on Raspberry Pi OS when ROS2
# runs in Docker. It remains available for Ubuntu/native ROS2 installations.
ENABLE_ROS2_BRIDGE = True
ROS2_NODE_NAME = os.getenv("ROBOT_HEAD_ROS2_NODE_NAME", "robot_head_bridge")

# Docker-ready bridge. The host Pi application owns Picamera2 and the RP2350
# serial port; the host-network ROS2 container connects to this local TCP port.
# Binding to 127.0.0.1 keeps the command API private to the Pi itself.
ENABLE_ROS_COMMAND_SERVER = _env_bool(
    "ROBOT_HEAD_ENABLE_ROS_COMMAND_SERVER",
    True,
)
ROS_COMMAND_SERVER_HOST = os.getenv(
    "ROBOT_HEAD_ROS_COMMAND_HOST",
    "127.0.0.1",
)
ROS_COMMAND_SERVER_PORT = _env_int(
    "ROBOT_HEAD_ROS_COMMAND_PORT",
    8765,
)

MANUAL_PAN_STEP_DEG = 5.0
MANUAL_TILT_STEP_DEG = 2.0
MANUAL_GESTURE_COUNT = 3
MANUAL_FACE_HOLD_MS = 4000
MANUAL_TEXT_HOLD_MS = 5000
MANUAL_TEXT_MESSAGE = "Hello from Daisy"
MANUAL_TEXT_ITALIC = False
OOPSIE_DAISY_HOLD_MS = 5000

DEFAULT_GESTURE_COUNT = 3
MAX_GESTURE_COUNT = 8
DEFAULT_GESTURE_HOLD_MS = 0

# =====================================================
# Serial
# =====================================================

SERIAL_PORT = "auto"
# SERIAL_PORT = "/dev/ttyACM0"
BAUDRATE = 115200

# =====================================================
# Human tracking
# =====================================================

POSE_DETECTION_CONFIDENCE = 0.70
POSE_TRACKING_CONFIDENCE = 0.70
POSE_LANDMARK_VISIBILITY = 0.45

ENABLE_FACE_FALLBACK = True
STRICT_TORSO_VALIDATION = False

MIN_BODY_HEIGHT_RATIO = 0.16
MIN_BODY_WIDTH_RATIO = 0.08
MIN_UPPER_BODY_HEIGHT_RATIO = 0.10
MIN_UPPER_BODY_WIDTH_RATIO = 0.08
MIN_VISIBLE_POSE_POINTS = 5

# =====================================================
# Target selection
# =====================================================

# The selector uses the head first for both horizontal and vertical tracking:
# eyes -> nose -> face centre -> ears -> shoulders -> upper body -> torso -> body.
TARGET_POINT_SMOOTHING_ALPHA = 0.35

# =====================================================
# Distance estimation
# =====================================================

# "auto" tries shoulder width, then face width, then the fixed fallback.
# Other supported values: "shoulder", "face", "fixed", "none".
TARGET_DISTANCE_MODE = "auto"

ASSUMED_SHOULDER_WIDTH_M = 0.40
ASSUMED_FACE_WIDTH_M = 0.16
DEFAULT_TARGET_DISTANCE_M = 2.00
MIN_TARGET_DISTANCE_M = 0.50
MAX_TARGET_DISTANCE_M = 6.00

DISTANCE_SMOOTHING_ALPHA = 0.20
MAX_DISTANCE_CHANGE_PER_FRAME_M = 0.30

# Reject very small landmark widths because they produce unstable distance values.
MIN_SHOULDER_WIDTH_PIXELS = 35.0
MIN_FACE_WIDTH_PIXELS = 30.0

# =====================================================
# Camera-to-head geometry
# =====================================================

# Position of the head pan/tilt pivot relative to the camera optical centre.
# Camera coordinates: +X right, +Y down, +Z forward.
# The default says the head pivot is 20 cm above the fixed camera.
HEAD_PIVOT_OFFSET_X_M = 0.00
HEAD_PIVOT_OFFSET_Y_M = -0.30
HEAD_PIVOT_OFFSET_Z_M = 0.00

# Small installation corrections. Leave at zero first, then tune if required.
CAMERA_TO_HEAD_YAW_BIAS_DEG = 0.0
CAMERA_TO_HEAD_PITCH_BIAS_DEG = 0.0

# =====================================================
# Head pan servo
# =====================================================

HEAD_PAN_CENTER_ANGLE = 90.0
HEAD_PAN_MIN_ANGLE = 0.0
HEAD_PAN_MAX_ANGLE = 180.0
HEAD_PAN_SOFT_LIMIT_FROM_CENTER_DEG = 45.0
HEAD_PAN_SERVO_DIRECTION = 1
CONTROL_REVERSE_X = False

# =====================================================
# Head tilt servo
# =====================================================

HEAD_TILT_CENTER_ANGLE = 98
HEAD_TILT_MIN_ANGLE = 75
HEAD_TILT_MAX_ANGLE = 120.0
# The smaller side around the 90-degree neutral is 15 degrees.
HEAD_TILT_SOFT_LIMIT_FROM_CENTER_DEG = 15.0
HEAD_TILT_SERVO_DIRECTION = 1
CONTROL_REVERSE_Y = False

# =====================================================
# Smooth pan/tilt tracking
# =====================================================

PAN_ANGLE_DEADBAND_DEG = 0.50
TILT_ANGLE_DEADBAND_DEG = 0.50

PAN_ERROR_SMOOTHING_ALPHA = 0.35
TILT_ERROR_SMOOTHING_ALPHA = 0.25

PAN_MAX_TARGET_STEP_PER_UPDATE_DEG = 2.50
TILT_MAX_TARGET_STEP_PER_UPDATE_DEG = 1.80

SEND_INTERVAL_SEC = 0.02
MIN_PAN_CHANGE_TO_SEND_DEG = 0.70
MIN_TILT_CHANGE_TO_SEND_DEG = 0.70

# =====================================================
# Emotion detection
# =====================================================

EMOTION_ANALYZE_EVERY_N_FRAMES = 10
EMOTION_DETECTOR_BACKEND = "opencv"
EMOTION_ENFORCE_DETECTION = True

# =====================================================
# Gesture detection
# =====================================================

MAX_NUM_HANDS = 2
GESTURE_PROCESS_EVERY_N_FRAMES = 1
HAND_DETECTION_CONFIDENCE = 0.60
HAND_TRACKING_CONFIDENCE = 0.60

WAVE_HISTORY_SIZE = 20
WAVE_MIN_X_RANGE = 0.08
WAVE_MIN_DIRECTION_CHANGES = 1
WAVE_MIN_STEP = 0.008

OPEN_PALM_ENABLED = True
OPEN_PALM_MIN_FINGERS = 5
OPEN_PALM_HOLD_FRAMES = 30
HELLO_COOLDOWN_FRAMES = 30

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
    "DISGUST",
    "SLEEPING",
    "IDLE",
    "RUNNING",
    "DIZZY",
    "SIGMA",
    "SUNGLASSES",
    "THINKING",
]

SUPPORTED_GESTURES = [
    "NOD",
    "SUNGLASSES_NOD",
    "SIGMA_NOD",
    "SHAKE",
    "LOOK_AROUND",
    "CELEBRATE",
    "DANCE",
    "GREET",
    "DAISY_DANCE",
    "SLEEP",
    "WAKE_UP",
]
