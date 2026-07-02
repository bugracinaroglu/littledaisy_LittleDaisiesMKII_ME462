# Robot Head Project v10 — Control Modes, New Faces and RP2350 Gestures

This project uses a Raspberry Pi for camera/behavior/ROS commands and an RP2350
for the round LCD, servos, IMU behavior and non-blocking gesture execution.

## Added in this version

- New LCD faces: `SIGMA` and `SUNGLASSES`
- RP2350 head gestures with configurable repeat count
- Combined gestures: `SUNGLASSES_NOD` and `SIGMA_NOD`
- Optional face lock: `hold_ms`
- Less sensitive `RUNNING` face activation
- Manual keyboard controls for faces and gestures
- Raspberry Pi Python API and ROS2 topic/service support

The intentional mapping below is preserved:

```text
FACE:NEUTRAL -> CURIOUS
```

## Running the system

Upload **all files inside `microcontrollerside/`** to the RP2350 MicroPython
root. The RP2350 must have `main.py` at its root.

On the Raspberry Pi:

```bash
cd robot_head_project
python3 main.py
```

Click inside the OpenCV camera window before pressing keyboard controls.
Terminal output may continue scrolling; commands are read from the OpenCV
window, not typed into the terminal.

## Control modes

```text
1 -> AUTO
2 -> MANUAL
3 -> ROS
```

- `AUTO`: camera tracking, emotion and enabled autonomous behavior control the robot.
- `MANUAL`: OpenCV keyboard controls and direct Python calls are accepted.
- `ROS`: ROS2 callbacks are accepted.

Changing mode cancels the current RP2350 gesture and stops movement from the
previous command source.

## MANUAL keyboard controls

First press `2`, then use:

```text
J / L  -> pan left / right
I / K  -> tilt up / down
C      -> center
S      -> stop
A      -> arm wave
F      -> CURIOUS face
4      -> SIGMA face, locked for MANUAL_FACE_HOLD_MS
5      -> SUNGLASSES face, locked for MANUAL_FACE_HOLD_MS

N      -> NOD
O      -> SUNGLASSES_NOD
G      -> SIGMA_NOD
X      -> SHAKE
B      -> LOOK_AROUND
M      -> CELEBRATE
Z      -> SLEEP
W      -> WAKE_UP
0      -> cancel the active gesture

E      -> emergency stop and switch to MANUAL
Q      -> quit
```

Manual defaults are configured in `robot_head_project/config.py`:

```python
MANUAL_GESTURE_COUNT = 2
MANUAL_FACE_HOLD_MS = 4000
```

## Raspberry Pi Python control API

The high-level API is in:

```text
robot_head_project/control/robot_head_interface.py
```

Examples using the existing `robot_head` object:

```python
robot_head.show_face("SIGMA", hold_ms=4000)
robot_head.show_face("SUNGLASSES", hold_ms=5000)

robot_head.nod_head(count=2)
robot_head.sunglasses_nod(count=2, hold_ms=4000)
robot_head.sigma_nod(count=3, hold_ms=5000)

robot_head.shake_head(count=2)
robot_head.look_around(count=1, hold_ms=3000)
robot_head.celebrate(count=2, hold_ms=4000)
robot_head.sleep(hold_ms=5000)
robot_head.wake_up(hold_ms=3000)
robot_head.cancel_gesture()
```

The default source is `MANUAL`. Therefore direct calls are accepted after:

```python
mode_manager.set_mode(ControlMode.MANUAL)
```

AUTO and ROS callers pass their own source explicitly:

```python
robot_head.nod_head(count=2, source=ControlMode.AUTO)
robot_head.sigma_nod(count=2, hold_ms=4000, source=ControlMode.ROS)
```

### Parameter meaning

- `count=2`: two complete movement pairs. For `NOD`, one pair is down/up.
- `hold_ms=4000`: prevent RP2350 IMU faces such as `RUNNING` or `DIZZY`
  from replacing the commanded face for 4000 ms.
- `hold_ms=0`: no timed face lock. An active gesture still blocks IMU face
  overrides until its movement ends.

During an active RP2350 gesture, incoming tracking pose commands are ignored.
Use `cancel_gesture()`, `STOP` or `CENTER` to interrupt it.

## Direct serial commands

```text
FACE:SIGMA
FACE:SIGMA,4000
FACE:SUNGLASSES,5000

GESTURE:NOD,2,0
GESTURE:SUNGLASSES_NOD,2,4000
GESTURE:SIGMA_NOD,3,5000
GESTURE:SHAKE,2,0
GESTURE:LOOK_AROUND,1,3000
GESTURE:CELEBRATE,2,4000
GESTURE:SLEEP,1,5000
GESTURE:WAKE_UP,1,3000
GESTURE:CANCEL

HEAD_POSE:90,40
HEAD_PAN:90
HEAD_TILT:40
ARM:WAVE
CENTER
STOP
```

## RP2350 gesture tuning

Gesture motion is executed by:

```text
microcontrollerside/head_gesture_controller.py
```

Tune the movement in `microcontrollerside/config.py`:

```python
GESTURE_DEFAULT_REPEAT_COUNT = 2
GESTURE_MAX_REPEAT_COUNT = 8

GESTURE_NOD_UP_OFFSET_DEG = 7.0
GESTURE_NOD_DOWN_OFFSET_DEG = -7.0
GESTURE_NOD_DWELL_MS = 120

GESTURE_SHAKE_LEFT_OFFSET_DEG = -8.0
GESTURE_SHAKE_RIGHT_OFFSET_DEG = 8.0
GESTURE_SHAKE_DWELL_MS = 130

GESTURE_LOOK_LEFT_OFFSET_DEG = -18.0
GESTURE_LOOK_RIGHT_OFFSET_DEG = 18.0
GESTURE_LOOK_DWELL_MS = 320
```

If the physical tilt direction is reversed, swap the signs of the nod offsets.
All targets are clamped to the configured safe servo limits.

## RUNNING face behavior

`RUNNING` now requires stronger and longer continuous motion before replacing
the base face:

```python
RUNNING_DELTA_MAG_THRESHOLD = 0.35
RUNNING_DELTA_MAG_STRONG_THRESHOLD = 1.10
RUNNING_START_COUNT = 6
RUNNING_STOP_COUNT = 10
RUNNING_ARM_MIN_ACTIVE_MS = 700
RUNNING_FACE_MIN_ACTIVE_MS = 1200
```

Face priority is effectively:

```text
active gesture / hold_ms lock
    > IMU DIZZY
    > IMU RUNNING
    > commanded base face
```

In `MANUAL` and `ROS` modes, local RP2350 IMU face/arm overrides remain disabled.

## ROS2 interfaces

Enable the bridge only when ROS2 Python packages are available:

```python
ENABLE_ROS2_BRIDGE = True
```

Main topics:

```text
/robot_head/control_mode   std_msgs/String
/robot_head/face           std_msgs/String
/robot_head/gesture        std_msgs/String
/robot_head/pan            std_msgs/Float64
/robot_head/tilt           std_msgs/Float64
/robot_head/pose           std_msgs/Float64MultiArray
/robot_head/center         std_msgs/Empty
/robot_head/stop           std_msgs/Empty
/robot_head/arm_wave       std_msgs/Empty
/robot_head/cancel_gesture std_msgs/Empty
```

Examples:

```bash
ros2 topic pub --once /robot_head/control_mode std_msgs/msg/String "{data: ROS}"
ros2 topic pub --once /robot_head/face std_msgs/msg/String "{data: 'SIGMA,4000'}"
ros2 topic pub --once /robot_head/gesture std_msgs/msg/String "{data: 'NOD,2,0'}"
ros2 topic pub --once /robot_head/gesture std_msgs/msg/String "{data: 'SUNGLASSES_NOD,2,4000'}"
ros2 topic pub --once /robot_head/gesture std_msgs/msg/String "{data: 'SIGMA_NOD,3,5000'}"
```

Trigger services are also provided for center, stop, arm wave, nod,
sunglasses nod, sigma nod and gesture cancellation.
