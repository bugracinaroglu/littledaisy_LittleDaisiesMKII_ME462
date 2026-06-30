# Robot Head Project v6

Version 6 uses a **fixed Raspberry Pi fisheye camera** and controls two absolute head axes:

- **Pan:** left/right head rotation
- **Tilt:** up/down head rotation

The old head-mounted-camera branch has been removed from both the Raspberry Pi and RP2350 code.

## Main changes

- Uses `robot_head_project/calibration/calibration.json` automatically.
- Camera resolution is `1296 x 972`, matching the supplied calibration.
- Uses `cv2.fisheye` correction with `balance = 0.0`.
- Tracks the head first for both pan and tilt:
  1. midpoint of both eyes
  2. nose
  3. face centre
  4. ears
  5. shoulders
  6. upper body
  7. torso
  8. body centre
- Estimates distance using shoulder width, then face width, then a fixed fallback.
- Compensates for the camera being below the head pivot using a simple configurable offset.
- Sends the desired head-pan angle and direct tilt-servo angle with `HEAD_POSE:pan,tilt`.
- RP2350 controls the pan and tilt servos non-blockingly.

## Project structure

```text
head_project_v6/
├── README.md
├── robot_head_project/
│   ├── main.py
│   ├── config.py
│   ├── camera.py
│   ├── calibration/
│   │   └── calibration.json
│   ├── behavior/
│   │   └── behavior_manager.py
│   ├── control/
│   │   ├── command_sender.py
│   │   ├── head_pose_mapper.py
│   │   └── smoothing.py
│   ├── vision/
│   │   ├── human_tracker.py
│   │   ├── target_selector.py
│   │   ├── distance_estimator.py
│   │   ├── gesture_detector.py
│   │   └── emotion_detector.py
│   └── tools/
│       └── preview_calibration.py
└── microcontrollerside/
    ├── main.py
    ├── config.py
    ├── head_controller.py
    ├── servo_controller.py
    ├── serial_parser.py
    └── remaining LCD, arm, touch and IMU files
```

## Wiring

Default RP2350 signal pins:

| Device | Signal GPIO |
|---|---:|
| Head pan servo | GPIO 28 |
| Head tilt servo | GPIO 20 |
| Left arm servo | GPIO 26 |
| Right arm servo | GPIO 27 |

GPIO 20 was selected because it does not overlap the LCD, touch, IMU, arm or existing pan-servo pins used by the supplied code. It can be changed in:

```python
# microcontrollerside/config.py
HEAD_TILT_SERVO_PIN = 20
```

### Servo-power warning

Do not power the servos from the RP2350 3.3 V pin. Use a suitable external servo supply and connect:

- external supply ground
- RP2350 ground
- all servo grounds

together as a common ground. Test the tilt mechanism first with conservative angle limits.

## Raspberry Pi setup

The calibration file is already in the correct directory. From the project folder:

```bash
cd robot_head_project
python3 main.py
```

For a virtual environment on Raspberry Pi OS, Picamera2 is commonly made available through system packages:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Calibration preview:

```bash
cd robot_head_project
python3 tools/preview_calibration.py --balance 0
```

## RP2350 installation

Upload every file inside `microcontrollerside/` to the RP2350 MicroPython root directory. The board should contain `main.py` at its root.

The RP2350 accepts:

```text
HEAD_POSE:90,90
HEAD_PAN:90
HEAD_TILT:90
HEAD:90            # manual compatibility; pan only
FACE:HAPPY
ARM:WAVE
CENTER
STOP
```

The Raspberry Pi normally sends `HEAD_POSE`.

## Important Raspberry Pi settings

All main tuning values are in `robot_head_project/config.py`.

### Camera calibration

```python
FRAME_WIDTH = 1296
FRAME_HEIGHT = 972
FISHEYE_BALANCE = 0.0
CAMERA_CALIBRATION_FILE = .../calibration/calibration.json
```

Use the calibrated resolution unless the camera is recalibrated. Merely increasing the resolution can invalidate the calibration if the sensor crop mode changes.

### Camera-to-head offset

```python
HEAD_PIVOT_OFFSET_X_M = 0.00
HEAD_PIVOT_OFFSET_Y_M = -0.20
HEAD_PIVOT_OFFSET_Z_M = 0.00
```

Camera coordinates are:

- `+X`: right
- `+Y`: down
- `+Z`: forward

Therefore `Y = -0.20` means the head pivot is 20 cm above the camera. Change this value after measuring the real mechanism.

The correction is intentionally simple. The selected image pixel gives the viewing ray. An approximate distance gives a target point, and the 20 cm offset is subtracted before calculating pan and tilt.

### Distance estimate

```python
TARGET_DISTANCE_MODE = "auto"
ASSUMED_SHOULDER_WIDTH_M = 0.40
ASSUMED_FACE_WIDTH_M = 0.16
DEFAULT_TARGET_DISTANCE_M = 2.00
```

`auto` uses:

1. shoulder width
2. face width
3. fixed fallback distance

Supported modes are `auto`, `shoulder`, `face`, `fixed`, and `none`. With `none`, the camera ray is used directly and metric offset compensation is disabled.

### Enable or disable tilt tracking

```python
ENABLE_UP_DOWN_HUMAN_TRACKING = True
```

It can also be toggled while the Raspberry Pi program is running by pressing `u`.

### Pan gear conversion and mechanical limits

The Raspberry Pi sends a **desired head pan angle** centred at 90 degrees. The
RP2350 converts it to the physical pan-servo angle because the external gears
reverse direction and have a `1:1.7` ratio:

```python
servo_angle = 90.0 - 1.7 * (requested_head_angle - 90.0)
```

The conversion is applied only to the offset from neutral. Examples:

- Head command `100°` -> pan servo target `73°`
- Head command `90°` -> pan servo target `90°`
- Head command `70°` -> pan servo target `124°`

RP2350 settings:

```python
HEAD_PAN_SERVO_NEUTRAL_ANGLE = 90.0
HEAD_PAN_MIN_LIMIT_ANGLE = 0.0
HEAD_PAN_MAX_LIMIT_ANGLE = 180.0
HEAD_PAN_GEAR_RATIO = 1.7
HEAD_PAN_GEAR_REVERSES_DIRECTION = True

HEAD_TILT_NEUTRAL_ANGLE = 90.0
HEAD_TILT_MIN_LIMIT_ANGLE = 73.0
HEAD_TILT_MAX_LIMIT_ANGLE = 105.0
```

The Pi also limits tilt to `73–105°`. Pan commands remain head angles; the
current Pi soft limit is `90 ± 45°`, which maps to safe servo targets of
`13.5–166.5°`. Final physical clamping is always performed by the RP2350.

### Reversing motion

If a servo moves in the wrong direction, change:

```python
HEAD_PAN_SERVO_DIRECTION = -1
HEAD_TILT_SERVO_DIRECTION = -1
```

Runtime keys are:

- `d`: reverse pan servo direction
- `k`: reverse tilt servo direction
- `r`: reverse camera X control
- `y`: reverse camera Y control

## First hardware test

1. Keep the servo horns disconnected or allow the mechanism to move freely.
2. Confirm both servos centre with `CENTER`.
3. Send `HEAD_PAN:80`, then `HEAD_PAN:100`. These are requested **head** angles; the RP2350 should command the pan servo to `107°` and `73°` respectively.
4. Send `HEAD_TILT:73`, `HEAD_TILT:90`, then `HEAD_TILT:105`.
5. Confirm direction, neutral position, gear motion, and mechanical clearance.
6. Reduce the RP2350 angle limits before attaching the mechanism if either axis approaches a hard stop.
7. Start the Raspberry Pi tracking program only after the manual test succeeds.

## Notes

- The 20 cm compensation depends on approximate distance, but it is not used for general 3D reconstruction.
- Shoulder and face dimensions vary between people; the estimate is filtered and bounded because it only needs to improve the small camera/head parallax correction.
- When no reliable size measurement exists, the system continues with `DEFAULT_TARGET_DISTANCE_M` instead of stopping.
