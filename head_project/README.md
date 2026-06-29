# Little Daisies MKII – Robot Head Project

This repository contains five development versions of the **Little Daisies MKII robot head software**.

The system uses a camera to detect and follow a person. It can control the head and arm servos, recognize hand gestures and facial emotions, display animated faces, detect motion with an IMU, and communicate with an RP2350 microcontroller.

## Project Structure

Some earlier versions do not contain every file shown below. This is the complete structure used by the latest versions.

```text
head_proje_vX/
├── robot_head_project/                 # Computer or Raspberry Pi side
│   ├── main.py                         # Main program loop
│   ├── config.py                       # Camera, tracking, and control settings
│   ├── camera.py                       # Camera input and fisheye correction
│   ├── visualizer.py                   # OpenCV visualization
│   ├── requirements.txt                # Python dependencies
│   ├── vision/
│   │   ├── human_tracker.py            # Human and body tracking
│   │   ├── target_selector.py          # Tracking target selection
│   │   ├── gesture_detector.py         # Hand gesture detection
│   │   └── emotion_detector.py         # Facial emotion detection
│   ├── control/
│   │   ├── command_sender.py           # Serial command transmission
│   │   ├── head_angle_mapper.py        # Target-to-servo angle conversion
│   │   └── smoothing.py                # Smoothing and rate limiting
│   └── behavior/
│       └── behavior_manager.py         # Head, face, and arm behavior control
│
└── microcontrollerside/                # RP2350 MicroPython side
    ├── main.py                         # Main microcontroller loop
    ├── config.py                       # Hardware and motion settings
    ├── servo_controller.py             # Basic servo control
    ├── head_controller.py              # Head servo control
    ├── arm_controller.py               # Arm control and animations
    ├── face_renderer.py                # LCD facial expressions
    ├── imu_motion_detector.py          # IMU movement detection
    ├── serial_parser.py                # Serial command parsing
    ├── rp2350_touch_lcd_128.py         # LCD, touch, and IMU drivers
    └── touch_test.py                   # Touch-screen test
```

## Computer / Raspberry Pi Side

### `main.py`

Starts all computer-side modules and runs the main loop. It reads the camera, runs detection, selects a target, calculates the head command, sends serial commands, and displays the OpenCV window.

Functions: `create_emotion_detector`, `main`

### `config.py`

Contains the camera, tracking, gesture, emotion, servo, serial, and feature settings. Most system adjustments are made here.

### `camera.py`

Provides one camera interface for USB webcams and Raspberry Pi cameras. It also supports image flipping, cropping, manual defish correction, and calibrated fisheye correction.

Class `Camera`: `__init__`, `_init_opencv_camera`, `_init_picamera2`, `is_opened`, `toggle_horizontal_flip`, `toggle_vertical_flip`, `read`, `release`, `_read_opencv`, `_read_picamera2`, `_apply_distortion_correction`, `_center_crop_and_resize`, `_apply_manual_defish`, `_build_manual_defish_maps`, `_apply_calibrated_fisheye_undistort`, `_build_fisheye_maps`

### `visualizer.py`

Draws body landmarks, bounding boxes, gestures, emotions, selected targets, servo information, serial status, and FPS on the output image.

Class `Visualizer`: `__init__`, `draw_text_box`, `draw_human`, `draw_emotion`, `draw_gesture`, `draw_target`, `draw_control`, `draw_fps`

### `requirements.txt`

Lists the Python packages used by the robot-head project, including NumPy, OpenCV, MediaPipe, DeepFace, TensorFlow, Protobuf, and PySerial. Picamera2 and libcamera are installed through Raspberry Pi OS with `apt`, not through `pip`.

## Vision Modules

### `vision/human_tracker.py`

Uses MediaPipe Pose to detect a person and calculate body, torso, and upper-body centers. It can use OpenCV face detection when pose detection is not reliable.

Class `HumanTracker`: `__init__`, `_empty_result`, `_to_norm`, `_average_points`, `_get_point`, `_make_bbox_from_points`, `_bbox_center`, `_bbox_size_ratios`, `_detect_face_fallback`, `_full_torso_center`, `_upper_body_center`, `_has_valid_upper_body`, `update`, `close`

### `vision/target_selector.py`

Chooses the best available tracking point. The priority is torso, upper body, body center, face fallback, and emotion-detector face.

Class `TargetSelector`: `__init__`, `_empty_target`, `_make_target`, `select`

### `vision/gesture_detector.py`

Uses MediaPipe Hands to detect hand waving and open-palm gestures.

Class `GestureDetector`: `__init__`, `_empty_result`, `_distance`, `_get_hand_center`, `_count_extended_fingers`, `_count_direction_changes`, `_detect_wave`, `update`, `close`

### `vision/emotion_detector.py`

Uses DeepFace to estimate the dominant facial emotion and return the detected face center.

Class `EmotionDetector`: `__init__`, `_empty_result`, `_face_center_from_region`, `update`

## Control Modules

### `control/command_sender.py`

Opens the serial connection and sends head, face, arm, center, and stop commands to the RP2350.

Class `CommandSender`: `__init__`, `_auto_find_serial_port`, `_open_serial_connection`, `is_connected`, `send_raw`, `send_head_angle`, `send_face`, `send_arm_wave`, `send_center`, `send_stop`, `close`

### `control/head_angle_mapper.py`

Converts the target position in the image into a servo target angle. It supports fixed-camera and head-mounted-camera control, deadband, direction reversal, smoothing, and angle limits.

Class `HeadAngleMapper`: `__init__`, `reset_center`, `toggle_servo_direction`, `toggle_control_reverse_x`, `get_fx_pixels`, `norm_error_to_angle_error_deg`, `_apply_angle_limits`, `_hold_current`, `update`

### `control/smoothing.py`

Contains common control filters.

Function: `clamp`

Class `LowPassFilter`: `__init__`, `reset`, `update`

Class `RateLimiter`: `__init__`, `reset`, `update`

## Behavior Module

### `behavior/behavior_manager.py`

Combines tracking, gesture, and emotion results. It decides when to move the head, wave the arm, change the face, or enter the sleeping state.

Class `BehaviorManager`: `__init__`, `_emotion_to_face`, `_get_human_detected`, `update`

## RP2350 Microcontroller Side

### `microcontrollerside/main.py`

Initializes the LCD, touch controller, servos, serial parser, and IMU. It handles incoming commands and updates all hardware without blocking the main loop.

Functions: `init_lcd_and_face`, `init_touch`, `touch_pressed`, `init_head_controller`, `init_arm_controller`, `init_imu_motion_detector`, `apply_special_face`, `handle_command`, `run`

### `microcontrollerside/config.py`

Contains RP2350 pin assignments, servo limits, face settings, arm animations, and IMU thresholds.

### `microcontrollerside/servo_controller.py`

Provides the reusable PWM servo controller. It converts angles to PWM duty values and moves a servo gradually toward a target.

Class `ServoController`: `__init__`, `_init_pwm`, `_clamp_angle`, `_angle_to_duty_ns`, `_write_angle`, `go_to_angle_immediate`, `set_target_angle`, `go_to_neutral`, `hold_current_position`, `is_at_target`, `update`, `deinit`

### `microcontrollerside/head_controller.py`

Uses `ServoController` to control the head servo, center it, stop it, and update its movement.

Class `HeadController`: `__init__`, `set_angle`, `center`, `stop`, `update`, `deinit`

### `microcontrollerside/arm_controller.py`

Controls the left and right arm servos. It provides neutral positioning, waving, and IMU-triggered running animations.

Class `ArmController`: `__init__`, `start_wave`, `set_running_active`, `center`, `stop`, `_enter_running`, `_both_at_target`, `_update_wave_motion`, `_update_running_motion`, `update`, `deinit`

### `microcontrollerside/face_renderer.py`

Draws and animates the robot faces on the round LCD. It supports normal expressions, blinking, transitions, wave reactions, running, and dizzy animations.

Class `FaceRenderer`: `__init__`, `set_face`, `set_motion_vector`, `trigger_wave_reaction`, `update`, `_update_auto_animation`, `_start_blink`, `_get_normal_blink_amount`, `_get_transition_face_and_blink`, `_clear`, `_safe_hline`, `_thick_line`, `_fill_circle`, `_fill_round_rect`, `_fill_triangle`, `_ellipse_outline`, `_draw_curve`, `_draw_label`, `_draw_blink_eye`, `_draw_round_eye`, `_draw_capsule_eye`, `_draw_flame_pupil`, `_draw_blush`, `_draw_star`, `_draw_face`, `_draw_neutral`, `_draw_idle`, `_draw_curious`, `_draw_happy`, `_draw_sad`, `_draw_angry`, `_draw_surprised`, `_draw_disgust`, `_draw_sleeping`, `_draw_running`, `_draw_dizzy`

### `microcontrollerside/imu_motion_detector.py`

Reads the QMI8658 IMU. It detects repeated movement for the running animation and rapid rotation for the dizzy face.

Function: `clamp`

Class `IMUMotionDetector`: `__init__`, `_init_imu`, `_empty_result`, `_vector_mag`, `_update_running_state`, `_screen_direction_from_acc_delta`, `_update_dizzy_state`, `update`

### `microcontrollerside/serial_parser.py`

Reads text commands from USB serial and converts them into head, arm, face, center, and stop commands.

Class `SerialParser`: `__init__`, `read_command`, `parse`

### `microcontrollerside/rp2350_touch_lcd_128.py`

Contains the low-level drivers for the 1.28-inch LCD, CST816T touch controller, and QMI8658 IMU.

Class `LCD_1inch28`: `__init__`, `write_cmd`, `write_data`, `set_bl_pwm`, `init_display`, `setWindows`, `show`, `Windows_show`, `write_text`

Class `Touch_CST816T`: `__init__`, `_read_byte`, `_read_block`, `_write_byte`, `WhoAmI`, `Read_Revision`, `Stop_Sleep`, `Reset`, `Set_Mode`, `get_point`, `Int_Callback`, `Timer_callback`

Class `QMI8658`: `__init__`, `_read_byte`, `_read_block`, `_read_u16`, `_write_byte`, `WhoAmI`, `Read_Revision`, `Config_apply`, `_to_signed_16bit`, `Read_Raw_XYZ`, `Read_XYZ`

Functions: `Touch_HandWriting`, `Touch_Gesture`, `DOF_READ`, `run`

### `microcontrollerside/touch_test.py`

A standalone test script that displays the detected touch coordinates and touch count on the LCD.

## Computer-Side Configuration

The following settings are in `robot_head_project/config.py`.

### Camera

- `CAMERA_BACKEND`: Selects `opencv` for a USB webcam or `picamera2` for a Raspberry Pi ribbon camera.
- `CAMERA_PROFILE`: Labels the camera as `usb_webcam`, `pi_v2`, or `pi_fisheye`. The current code mainly uses it as profile information; actual operation is controlled by the backend and correction settings.
- `CAMERA_INDEX`: Selects the OpenCV camera device. Try `1` or `2` if camera `0` is not correct.
- `FRAME_WIDTH`, `FRAME_HEIGHT`: Change the camera resolution. Higher values provide more detail but require more processing.
- `FLIP_FRAME_HORIZONTAL`, `FLIP_FRAME_VERTICAL`: Mirror or vertically rotate the image.
- `CAMERA_HORIZONTAL_FOV_DEG`: Changes the conversion between image error and servo angle in fixed-camera mode.
- `WINDOW_NAME`: Changes the OpenCV window title.
- `CAMERA_MOUNT_MODE`: Use `fixed` when the camera does not rotate with the head, or `head_mounted` when it is attached to the head.

### Fisheye Correction

- `FISHEYE_CORRECTION_MODE`: Selects `none`, `crop`, `defish`, or `calibrated` correction.
- `FISHEYE_CROP_SCALE`: Lower values crop more of the image edges.
- `DEFISH_INPUT_DIAGONAL_FOV_DEG`: Sets the original fisheye camera field of view.
- `DEFISH_OUTPUT_DIAGONAL_FOV_DEG`: Lower values produce a narrower and less distorted output; higher values keep a wider view.
- `DEFISH_STRENGTH`: Higher values apply more manual fisheye correction.
- `DEFISH_ZOOM`: Higher values zoom in; lower values keep a wider image.
- `FISHEYE_CAMERA_MATRIX`, `FISHEYE_DIST_COEFFS`: Add real calibration values for calibrated correction.
- `FISHEYE_BALANCE`: Controls how much of the original fisheye field of view is preserved in calibrated mode.

### Feature Switches

- `ENABLE_HEAD_TRACKING`, `ENABLE_ARM_WAVE`, `ENABLE_LCD_FACE`: Enable or disable the main robot behaviors.
- `HEAD_SERVO_ENABLED`, `ARM_SERVOS_ENABLED`, `LCD_ENABLED`: Enable or disable the related RP2350 hardware commands.
- `ENABLE_HUMAN_TRACKING`, `ENABLE_EMOTION`, `ENABLE_GESTURE`: Enable or disable individual vision modules.
- `ENABLE_SERIAL`: Use `False` for vision-only testing without the RP2350.

### Serial Communication

- `SERIAL_PORT`: Use `auto` for automatic detection or enter a port such as `/dev/ttyACM0`.
- `BAUDRATE`: Must match the communication speed used by the connected device.

### Human Tracking

- `POSE_DETECTION_CONFIDENCE`: Higher values reduce weak detections but may miss difficult poses.
- `POSE_TRACKING_CONFIDENCE`: Higher values require more reliable tracking between frames.
- `ENABLE_FACE_FALLBACK`: Allows face detection when body tracking fails.
- `STRICT_TORSO_VALIDATION`: When enabled, requires a more complete torso before accepting the person.
- `MIN_BODY_HEIGHT_RATIO`, `MIN_BODY_WIDTH_RATIO`: Reject body detections that are too small.
- `MIN_UPPER_BODY_HEIGHT_RATIO`, `MIN_UPPER_BODY_WIDTH_RATIO`: Reject upper-body detections that are too small.
- `MIN_VISIBLE_POSE_POINTS`: Higher values require more visible body landmarks.

### Emotion Detection

- `EMOTION_ANALYZE_EVERY_N_FRAMES`: Higher values reduce processing load but update emotions less often.
- `EMOTION_DETECTOR_BACKEND`: Selects the DeepFace detector backend.
- `EMOTION_ENFORCE_DETECTION`: When enabled, DeepFace requires a valid face before returning a result.

### Gesture Detection

- `MAX_NUM_HANDS`: Sets the maximum number of detected hands.
- `GESTURE_PROCESS_EVERY_N_FRAMES`: Higher values reduce processing load but make gesture updates slower.
- `HAND_DETECTION_CONFIDENCE`, `HAND_TRACKING_CONFIDENCE`: Higher values require more reliable hand detections.
- `WAVE_HISTORY_SIZE`: Changes how many recent hand positions are stored.
- `WAVE_MIN_X_RANGE`: Higher values require a wider horizontal hand movement.
- `WAVE_MIN_DIRECTION_CHANGES`: Higher values require more left-right direction changes.
- `WAVE_MIN_STEP`: Higher values ignore smaller hand movements.
- `OPEN_PALM_ENABLED`: Enables or disables open-palm detection.
- `OPEN_PALM_MIN_FINGERS`: Sets the required number of extended fingers.
- `OPEN_PALM_HOLD_FRAMES`: Higher values require the palm to stay open longer.
- `HELLO_COOLDOWN_FRAMES`: Higher values increase the delay before another greeting is accepted.

### Head Servo and Tracking

- `HEAD_SERVO_CENTER_ANGLE`: Sets the forward-facing head angle.
- `HEAD_SERVO_MIN_ANGLE`, `HEAD_SERVO_MAX_ANGLE`: Set the physical servo limits.
- `HEAD_SERVO_SOFT_LIMIT_FROM_CENTER_DEG`: Limits normal movement around the center angle for safety.
- `HEAD_SERVO_DIRECTION`: Change between `1` and `-1` if the servo moves in the wrong direction.
- `CONTROL_REVERSE_X`: Reverses the horizontal image error without changing the servo configuration.
- `DEADBAND_NORM`: Higher values create a larger center area in which the head does not move.
- `DEADBAND_PIXELS`: Present in the configuration, but the current controller uses `DEADBAND_NORM`.
- `ERROR_SMOOTHING_ALPHA`: Higher values produce smoother but slower tracking; lower values react faster.
- `SEND_INTERVAL_SEC`: Lower values allow serial commands to be sent more often.
- `MIN_ANGLE_CHANGE_TO_SEND`: Higher values reduce small and repeated servo commands.
- `MAX_TARGET_STEP_PER_SEND`: Higher values allow faster head-angle changes; lower values make movement smoother.
- `HEAD_MOUNTED_GAIN`: Higher values create larger correction steps in head-mounted mode.
- `HEAD_MOUNTED_MIN_STEP_DEG`: Sets the smallest movement step in head-mounted mode.
- `HEAD_MOUNTED_MAX_STEP_DEG`: Limits the largest movement step in head-mounted mode.

### LCD Faces

- `DEFAULT_FACE`: Sets the normal face shown during operation.
- `NO_HUMAN_FACE`: Sets the face shown after no person is detected.
- `SUPPORTED_FACES`: Defines the face names accepted by the computer-side behavior logic.

## Microcontroller-Side Configuration

The following settings are in `microcontrollerside/config.py`.

### General Hardware

- `LCD_ENABLED`, `TOUCH_ENABLED`, `HEAD_SERVO_ENABLED`, `ARM_SERVOS_ENABLED`: Enable or disable individual hardware modules.
- `TOUCH_FACE_TEST_ENABLED`: Allows face changes by touching the LCD during testing.
- `DEFAULT_FACE`: Sets the initial LCD face.
- `FACE_LIST`: Defines the faces available during the touch test.

### Common Servo Settings

- `SERVO_FREQ`: Sets the PWM frequency.
- `SERVO_MIN_US`, `SERVO_MAX_US`: Set the servo pulse-width range. Adjust carefully for the installed servo.
- `SERVO_MAX_ANGLE`: Sets the angle range used in pulse conversion.

### Head Servo

- `HEAD_SERVO_PIN`: Selects the RP2350 pin connected to the head servo.
- `HEAD_NEUTRAL_ANGLE`: Sets the centered head position.
- `HEAD_MIN_LIMIT_ANGLE`, `HEAD_MAX_LIMIT_ANGLE`: Protect the head mechanism from excessive movement.
- `HEAD_STEP_DEG`: Higher values move the servo farther during each update.
- `HEAD_MOVE_INTERVAL_MS`: Lower values update the servo more frequently and increase movement speed.

### Arm Servos

- `LEFT_ARM_SERVO_PIN`, `RIGHT_ARM_SERVO_PIN`: Select the arm-servo pins.
- `LEFT_ARM_NEUTRAL_ANGLE`, `RIGHT_ARM_NEUTRAL_ANGLE`: Set the resting arm positions.
- `LEFT_ARM_UP_ANGLE`, `RIGHT_ARM_UP_ANGLE`: Set the raised arm positions.
- `LEFT_ARM_MIN_LIMIT_ANGLE`, `LEFT_ARM_MAX_LIMIT_ANGLE`: Set the safe left-arm range.
- `RIGHT_ARM_MIN_LIMIT_ANGLE`, `RIGHT_ARM_MAX_LIMIT_ANGLE`: Set the safe right-arm range.
- `ARM_STEP_DEG`: Higher values make arm movement faster but less smooth.
- `ARM_MOVE_INTERVAL_MS`: Lower values update the arms more frequently.
- `ARM_WAVE_AMPLITUDE_DEG`: Higher values create a larger waving motion.
- `ARM_WAVE_INTERVAL_MS`: Lower values make the wave faster.
- `ARM_WAVE_CYCLES`: Sets the number of wave cycles.
- `USE_RIGHT_ARM_FOR_WAVE`: Selects which arm performs the greeting wave.

### IMU, Running, and Dizzy Motion

- `IMU_ENABLED`: Enables or disables IMU motion detection.
- `RUNNING_ARM_ENABLE`, `RUNNING_FACE_ENABLE`, `DIZZY_FACE_ENABLE`: Enable individual IMU reactions.
- `IMU_SAMPLE_INTERVAL_MS`: Lower values sample the IMU more frequently.
- `IMU_STARTUP_IGNORE_MS`: Ignores unstable IMU readings after startup.
- `RUNNING_DELTA_MAG_THRESHOLD`: Lower values make running detection more sensitive.
- `RUNNING_DELTA_MAG_STRONG_THRESHOLD`: Sets the movement level treated as a strong running event.
- `RUNNING_START_COUNT`: Lower values start the running state faster.
- `RUNNING_STOP_COUNT`: Higher values keep the running state active longer after motion decreases.
- `RUNNING_ARM_MIN_ACTIVE_MS`, `RUNNING_FACE_MIN_ACTIVE_MS`: Set the delay before running animations begin.
- `RUNNING_ARM_AMPLITUDE_DEG`: Sets the running arm movement size.
- `RUNNING_ARM_INTERVAL_MS`: Lower values make the running arm animation faster.
- `RUNNING_USE_RIGHT_ARM`: Enables the right arm during the running animation.
- `RUNNING_FACE_DIRECTION_SCALE`: Changes the sensitivity of the face movement direction.
- `RUNNING_FACE_REVERSE_X`, `RUNNING_FACE_REVERSE_Y`: Reverse the displayed movement direction.
- `RUNNING_FACE_SWAP_XY`: Swaps the IMU axes used by the face animation.
- `DIZZY_GYRO_THRESHOLD_DPS`: Lower values make the dizzy face easier to trigger.
- `DIZZY_FACE_DURATION_MS`: Sets how long the dizzy face remains active.

## Version Differences

### `head_proje_v1`

- First modular computer-side version.
- Uses an OpenCV camera and basic MediaPipe pose tracking.
- Supports emotion detection, wave detection, head mapping, and visualization.
- Serial communication is disabled by default.
- Does not include the RP2350 `microcontrollerside` folder.

### `head_proje_v2`

- Adds the complete RP2350 microcontroller-side software.
- Enables serial communication by default.
- Adds face fallback and more flexible torso/upper-body validation.
- Adds open-palm detection.
- Improves target selection and makes servo communication more responsive.

### `head_proje_v3`

- Adds `requirements.txt` to the computer-side project.
- Adds `imu_motion_detector.py` to the RP2350 side.
- Adds IMU-based running detection and rapid-rotation detection.
- Adds `RUNNING` and `DIZZY` LCD faces.
- Adds running arm animations and special-face priority handling.

### `head_proje_v4`

- Adds selectable `opencv` and `picamera2` camera backends.
- Adds USB, Pi Camera, and fisheye camera profiles.
- Adds crop, manual defish, and calibrated fisheye correction.
- Adds a dedicated control method for a camera mounted on the moving head.
- Adds upper-body priority to target selection.
- Uses USB webcam, fixed-camera, and no-fisheye-correction settings by default.

### `head_proje_v5`

- Uses the same main tracking and behavior architecture as V4.
- Changes the default camera to `picamera2` with the `pi_fisheye` profile.
- Enables manual defish correction.
- Uses `head_mounted` camera control.
- Disables emotion detection by default to reduce processing load.
- Uses faster and larger tracking steps than V4.
- Changes the Picamera2 stream format from `BGR888` to `RGB888`.
- The RP2350 microcontroller code is the same as V3 and V4.

## Raspberry Pi 5 Setup (Python 3.11)

The virtual environment is stored outside the repository at:

```text
~/python_envs/robot_head_shared_envs
```

Picamera2 and libcamera are installed through Raspberry Pi OS. The virtual environment is created with `--system-site-packages` so it can access them.

### First Installation or Clean Reinstallation

Install the required Raspberry Pi OS packages:

```bash
sudo apt update
sudo apt install -y \
    python3-venv \
    python3-picamera2 \
    libgl1 \
    libglib2.0-0 \
    libportaudio2
```

To completely recreate the environment, remove the old one first:

```bash
rm -rf ~/python_envs/robot_head_shared_envs
```

Create the Python 3.11 environment and install the project requirements:

```bash
mkdir -p ~/python_envs
python3.11 -m venv --system-site-packages ~/python_envs/robot_head_shared_envs
source ~/python_envs/robot_head_shared_envs/bin/activate
python -m pip install --upgrade pip setuptools wheel
cd ~/littledaisy_LittleDaisiesMKII_ME462/head_proje_v5/robot_head_project
python -m pip install --prefer-binary -r requirements.txt
```

### VS Code Interpreter

In VS Code, press `Ctrl+Shift+P`, select **Python: Select Interpreter**, and choose:

```text
/home/littledaisy/python_envs/robot_head_shared_envs/bin/python
```

### Run the Project

For every new terminal session:

```bash
source ~/python_envs/robot_head_shared_envs/bin/activate
cd ~/littledaisy_LittleDaisiesMKII_ME462/head_proje_v5/robot_head_project
python main.py
```

To leave the environment:

```bash
deactivate
```

### Quick Import Test

```bash
python -c "import cv2, mediapipe, tensorflow, serial; from deepface import DeepFace; from picamera2 import Picamera2; print('Environment OK')"
```
