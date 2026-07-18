# Robot Head Project v15 — ROS2 Docker Ready

> **ROS2 Docker kullanımı:** `ROS2_DOCKER_GUIDE_TR.md` dosyasını takip et.
> Bu sürümde Pi OS ana uygulaması kamera ve RP2350 seri portunu yönetir;
> host-network Docker container yalnızca ROS2 bridge node'unu çalıştırır.

The Raspberry Pi handles the camera, behavior decisions, manual keyboard input
and the optional ROS2 bridge. The RP2350 handles the round LCD, servos, IMU and
all non-blocking movement choreography.

## Main features

- Control modes: `AUTO`, `MANUAL`, `ROS`
- Faces: existing faces plus `SIGMA` and `SUNGLASSES`
- Configurable `count` and `hold_ms`
- RP2350 gestures:
  - `NOD`
  - `SUNGLASSES_NOD`
  - `SIGMA_NOD`
  - `SHAKE`
  - `LOOK_AROUND`
  - `CELEBRATE`
  - `DANCE`
  - `GREET`
  - `DAISY_DANCE`
  - `SLEEP`
  - `WAKE_UP`
- Reduced `RUNNING` face sensitivity
- Gesture/face locking against IMU overrides
- Manual keyboard controls
- High-level Python API
- Optional ROS2 topic and Trigger-service bridge

The intentional project behavior is preserved:

```text
FACE:NEUTRAL -> CURIOUS
```

## Installation

### RP2350

Upload **every file inside `microcontrollerside/`** to the root of the RP2350.
The following files must all be present, including:

```text
main.py
head_gesture_controller.py
arm_controller.py
face_renderer.py
config.py
```

Restart the RP2350 after uploading.

### Raspberry Pi

```bash
cd robot_head_project
python3 main.py
```

Click inside the OpenCV camera window before pressing keyboard commands. The
terminal may continue printing status messages; manual controls are read from
the OpenCV window, not typed into the terminal.

## Control modes

```text
1 -> AUTO
2 -> MANUAL
3 -> ROS
E -> emergency stop and switch to MANUAL
```

- `AUTO`: camera tracking, emotion and enabled autonomous behavior send commands.
- `MANUAL`: keyboard and direct Python API commands are accepted.
- `ROS`: ROS2 topic and service commands are accepted.

Changing mode cancels the current RP2350 gesture.

## Manual keyboard controls

First click the OpenCV window and press `2`.

### Basic controls

```text
J / L -> pan left / right
I / K -> tilt up / down
C     -> center head and arms
S     -> stop
A     -> arm wave
F     -> CURIOUS face
4     -> SIGMA face
5     -> SUNGLASSES face
0     -> cancel active gesture
Q     -> quit
```

### Gesture controls

```text
N -> NOD
O -> SUNGLASSES_NOD
G -> SIGMA_NOD
X -> SHAKE
B -> LOOK_AROUND
M -> CELEBRATE

6 -> DANCE
7 -> GREET
8 -> DAISY_DANCE

Z -> SLEEP
W -> WAKE_UP
```

Manual values are configured in `robot_head_project/config.py`:

```python
MANUAL_GESTURE_COUNT = 3
MANUAL_FACE_HOLD_MS = 4000
```

For example, with `MANUAL_GESTURE_COUNT = 3`:

- `DANCE` performs three complete right-centre-left-centre cycles.
- `GREET` performs three nods on the right and three nods on the left.
- `DAISY_DANCE` performs three head-dance cycles with arm rhythm.

## New movement behavior

### DANCE

The head turns and tilts simultaneously:

```text
right + up
center + down
left + up
center + down
restore starting pose
```

The face is automatically set to `SUNGLASSES`.

### GREET

```text
turn right
nod count times on the right
turn left
nod count times on the left
restore starting pose
```

The face is automatically set to `SUNGLASSES`.

### DAISY_DANCE

Uses the same simultaneous head choreography as `DANCE`, while both arms move
in opposite rhythmic directions. The arms return to neutral when the movement
finishes or is cancelled.

## Raspberry Pi Python API

The high-level interface is:

```text
robot_head_project/control/robot_head_interface.py
```

Examples using the existing `robot_head` object:

```python
robot_head.show_face("SIGMA", hold_ms=4000)
robot_head.show_face("SUNGLASSES", hold_ms=5000)

robot_head.nod_head(count=3)
robot_head.sunglasses_nod(count=3, hold_ms=4000)
robot_head.sigma_nod(count=3, hold_ms=5000)

robot_head.dance(count=3, hold_ms=7000)
robot_head.greet(nod_count=3, hold_ms=7000)
robot_head.daisy_dance(count=3, hold_ms=8000)

robot_head.shake_head(count=3)
robot_head.look_around(count=1, hold_ms=3000)
robot_head.celebrate(count=3, hold_ms=4000)
robot_head.sleep(hold_ms=5000)
robot_head.wake_up(hold_ms=3000)
robot_head.cancel_gesture()
```

Direct calls use `MANUAL` as the default source. Select MANUAL first:

```python
mode_manager.set_mode(ControlMode.MANUAL)
```

AUTO and ROS callers must identify their source:

```python
robot_head.dance(
    count=3,
    hold_ms=7000,
    source=ControlMode.AUTO,
)

robot_head.greet(
    nod_count=3,
    hold_ms=7000,
    source=ControlMode.ROS,
)
```

### Parameter meanings

- `count` for `DANCE` and `DAISY_DANCE`: number of full dance cycles.
- `nod_count` for `GREET`: number of nods performed on each side.
- `hold_ms`: timed LCD-face lock against IMU face replacement.
- An active gesture blocks IMU face replacement even if `hold_ms` is shorter
  than the movement duration.

## Direct serial commands

```text
GESTURE:DANCE,3,7000
GESTURE:GREET,3,7000
GESTURE:DAISY_DANCE,3,8000
GESTURE:CANCEL
```

The format is:

```text
GESTURE:NAME,count,hold_ms
```

Other examples:

```text
FACE:SIGMA,4000
FACE:SUNGLASSES,5000
GESTURE:NOD,3,0
GESTURE:SUNGLASSES_NOD,3,4000
GESTURE:SIGMA_NOD,3,5000
HEAD_POSE:90,90
ARM:WAVE
CENTER
STOP
```


## Smooth head-servo motion

Pan and tilt now use a non-blocking acceleration profile on the RP2350. The
controller updates once per servo PWM frame, accelerates gradually, and slows
automatically near the target. Tune these values in `microcontrollerside/config.py`:

```python
HEAD_PAN_MAX_SPEED_DEG_S = 140.0
HEAD_PAN_ACCEL_DEG_S2 = 400.0
HEAD_PAN_MOTION_UPDATE_INTERVAL_MS = 20

HEAD_TILT_MAX_SPEED_DEG_S = 100.0
HEAD_TILT_ACCEL_DEG_S2 = 300.0
HEAD_TILT_MOTION_UPDATE_INTERVAL_MS = 20
```

The measured tilt limits from this project are preserved:

```python
HEAD_TILT_MIN_LIMIT_ANGLE = 75.0
HEAD_TILT_MAX_LIMIT_ANGLE = 120
```

`LOOK_AROUND` uses the full mechanically reachable pan range calculated from
the servo limits and `HEAD_PAN_GEAR_RATIO` when this option is enabled:

```python
GESTURE_LOOK_AROUND_USE_FULL_RANGE = True
```

## RP2350 motion tuning

Tune the head movement in `microcontrollerside/config.py`:

```python
GESTURE_DANCE_PAN_OFFSET_DEG = 30.0
GESTURE_DANCE_TILT_UP_OFFSET_DEG = 9.0
GESTURE_DANCE_TILT_DOWN_OFFSET_DEG = -9.0
GESTURE_DANCE_DWELL_MS = 150

GESTURE_GREET_PAN_OFFSET_DEG = 35.0
GESTURE_GREET_NOD_UP_OFFSET_DEG = 9.0
GESTURE_GREET_NOD_DOWN_OFFSET_DEG = -9.0
GESTURE_GREET_TURN_DWELL_MS = 260
GESTURE_GREET_NOD_DWELL_MS = 130
```

Tune the two-arm dance in the same file:

```python
ARM_DANCE_AMPLITUDE_DEG = 35
ARM_DANCE_INTERVAL_MS = 160
ARM_DANCE_BEATS_PER_CYCLE = 4
```

All head and arm targets are clamped by the existing safe servo limits. Start
with the supplied values and observe the real mechanism before increasing any
angle or speed.

## IMU and face priority

During `DANCE`, `GREET`, `DAISY_DANCE` or any other active gesture:

```text
active gesture face
    > timed hold_ms face lock
    > DIZZY
    > RUNNING
    > normal commanded face
```

Therefore `RUNNING` and `DIZZY` cannot replace the `SUNGLASSES` face during the
new dance and greeting movements.

## ROS2

Enable the optional bridge in `robot_head_project/config.py` only when ROS2
Python packages are available:

```python
ENABLE_ROS2_BRIDGE = True
```

Generic gesture topic:

```bash
ros2 topic pub --once /robot_head/control_mode std_msgs/msg/String "{data: ROS}"
ros2 topic pub --once /robot_head/gesture std_msgs/msg/String "{data: 'DANCE,3,7000'}"
ros2 topic pub --once /robot_head/gesture std_msgs/msg/String "{data: 'GREET,2,7000'}"
ros2 topic pub --once /robot_head/gesture std_msgs/msg/String "{data: 'DAISY_DANCE,3,8000'}"
```

Trigger services use the default gesture count and `hold_ms=0`:

```bash
ros2 service call /robot_head/dance_service std_srvs/srv/Trigger "{}"
ros2 service call /robot_head/greet_service std_srvs/srv/Trigger "{}"
ros2 service call /robot_head/daisy_dance_service std_srvs/srv/Trigger "{}"
```

Use the generic `/robot_head/gesture` topic when custom `count` or `hold_ms`
values are needed.


## v13 motion behavior

All main moving gestures first travel to the neutral pose before their choreography starts. The loaded tilt axis also has separate, gentler limits for decreasing-angle (physical downward) motion. See `microcontrollerside/config.py` and `CHANGES_V13.md`.


---

## V14: LCD text and THINKING face

New high-level functions:

```python
robot_head.show_oopsie_daisy(hold_ms=5000)
robot_head.show_text("Hello from Daisy", hold_ms=4000, italic=False)
robot_head.show_thinking(hold_ms=4000)
```

Manual keys: `9` THINKING, `[` Oopsie Daisy, `]` configured general text.

See `LCD_TEXT_THINKING_GUIDE.md` for serial and ROS2 examples.


---

## V15: ROS2 Docker bridge

New runtime files:

```text
compose.ros2.yaml
compose.ros2.discovery.yaml
docker/ros2/Dockerfile
ros2_ws/src/robot_head_ros/
ROS2_DOCKER_GUIDE_TR.md
ROS2_API.md
```

The Raspberry Pi OS process starts a local command endpoint at
`127.0.0.1:8765`. The Docker container uses `network_mode: host` and talks to
that endpoint without opening the RP2350 serial port itself.

Quick start:

```bash
# Terminal 1 on the Pi
cd robot_head_project
python3 main.py

# Terminal 2 on the Pi, from project root
cp .env.ros2.example .env
docker compose -f compose.ros2.yaml up -d --build
```

See `ROS2_DOCKER_GUIDE_TR.md` for the complete remote-computer setup and
`ROS2_API.md` for all topics and services.
