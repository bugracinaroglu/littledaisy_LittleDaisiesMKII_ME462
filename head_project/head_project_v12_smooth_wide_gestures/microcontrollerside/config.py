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
    "SIGMA",
    "SUNGLASSES",
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

# Head axes use a time-based acceleration profile instead of fixed angle jumps.
# The servo output is updated once per 20 ms PWM frame, accelerates smoothly,
# and automatically slows as it approaches the target.
HEAD_PAN_MAX_SPEED_DEG_S = 140.0
HEAD_PAN_ACCEL_DEG_S2 = 400.0
HEAD_PAN_MOTION_UPDATE_INTERVAL_MS = 20

# Deprecated compatibility values for older helper code. The current head
# controller uses the speed/acceleration values above.
HEAD_PAN_STEP_DEG = 1.0
HEAD_PAN_MOVE_INTERVAL_MS = HEAD_PAN_MOTION_UPDATE_INTERVAL_MS

# Tilt is directly driven: incoming HEAD_TILT / HEAD_POSE tilt values are
# physical servo angles and are clamped to the measured safe range.
HEAD_TILT_NEUTRAL_ANGLE = 90
HEAD_TILT_MIN_LIMIT_ANGLE = 75.0
HEAD_TILT_MAX_LIMIT_ANGLE = 120
HEAD_TILT_MAX_SPEED_DEG_S = 100.0
HEAD_TILT_ACCEL_DEG_S2 = 300.0
HEAD_TILT_MOTION_UPDATE_INTERVAL_MS = 20

# Deprecated compatibility values for older helper code.
HEAD_TILT_STEP_DEG = 1.0
HEAD_TILT_MOVE_INTERVAL_MS = HEAD_TILT_MOTION_UPDATE_INTERVAL_MS

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
# Raised and delayed so normal handling vibration does not constantly replace
# commanded faces. Tune these only after observing real IMU values.
RUNNING_DELTA_MAG_THRESHOLD = 0.35
RUNNING_DELTA_MAG_STRONG_THRESHOLD = 1.10
RUNNING_START_COUNT = 6
RUNNING_STOP_COUNT = 10
RUNNING_ARM_MIN_ACTIVE_MS = 700
RUNNING_FACE_MIN_ACTIVE_MS = 1200

RUNNING_ARM_AMPLITUDE_DEG = 30
RUNNING_ARM_INTERVAL_MS = 100
RUNNING_USE_RIGHT_ARM = True

# Two-arm rhythm used only by DAISY_DANCE.
ARM_DANCE_AMPLITUDE_DEG = 35
ARM_DANCE_INTERVAL_MS = 160
ARM_DANCE_BEATS_PER_CYCLE = 4

RUNNING_FACE_DIRECTION_SCALE = 2.5
RUNNING_FACE_REVERSE_X = False
RUNNING_FACE_REVERSE_Y = False
RUNNING_FACE_SWAP_XY = False

DIZZY_GYRO_THRESHOLD_DPS = 420.0
DIZZY_FACE_DURATION_MS = 4500


# =====================================================
# RP2350 head gestures
# =====================================================

# One repeat means one complete pair: down/up for NOD and left/right for
# SHAKE/LOOK_AROUND. Serial commands may override the count per call.
GESTURE_DEFAULT_REPEAT_COUNT = 3
GESTURE_MAX_REPEAT_COUNT = 8
GESTURE_TARGET_TOLERANCE_DEG = 1.0

# Positive/negative direction can be swapped here if the physical tilt servo
# is mounted in the opposite direction.
GESTURE_NOD_UP_OFFSET_DEG = 10.0
GESTURE_NOD_DOWN_OFFSET_DEG = -10.0
GESTURE_NOD_DWELL_MS = 120

GESTURE_SHAKE_LEFT_OFFSET_DEG = -8.0
GESTURE_SHAKE_RIGHT_OFFSET_DEG = 8.0
GESTURE_SHAKE_DWELL_MS = 130

# True makes LOOK_AROUND visit the full mechanically reachable head-pan
# range calculated from the pan-servo limits and gear ratio. Set False to use
# the fallback offsets below.
GESTURE_LOOK_AROUND_USE_FULL_RANGE = True
GESTURE_LOOK_LEFT_OFFSET_DEG = -18.0
GESTURE_LOOK_RIGHT_OFFSET_DEG = 18.0
GESTURE_LOOK_DWELL_MS = 320

GESTURE_WAKE_UP_TILT_OFFSET_DEG = 6.0
GESTURE_WAKE_UP_DWELL_MS = 220

# DANCE / DAISY_DANCE: pan and tilt targets are commanded together.
# One count is one right-centre-left-centre cycle.
GESTURE_DANCE_PAN_OFFSET_DEG = 30.0
GESTURE_DANCE_TILT_UP_OFFSET_DEG = 9.0
GESTURE_DANCE_TILT_DOWN_OFFSET_DEG = -9.0
GESTURE_DANCE_DWELL_MS = 150

# GREET: turn right and nod count times, then turn left and nod count times.
GESTURE_GREET_PAN_OFFSET_DEG = 35.0
GESTURE_GREET_NOD_UP_OFFSET_DEG = 9.0
GESTURE_GREET_NOD_DOWN_OFFSET_DEG = -9.0
GESTURE_GREET_TURN_DWELL_MS = 260
GESTURE_GREET_NOD_DWELL_MS = 130

# Face lock starts when a FACE/GESTURE command is received. A value of zero
# means no timed lock; an active gesture still blocks IMU face overrides.
FACE_HOLD_MAX_MS = 600000
