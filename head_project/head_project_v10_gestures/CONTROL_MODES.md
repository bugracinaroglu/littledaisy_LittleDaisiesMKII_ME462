# Control Modes and Gesture Authority

Only one command source is active at a time:

- `AUTO`: camera/emotion/autonomous behavior
- `MANUAL`: OpenCV keyboard and direct Python API
- `ROS`: ROS2 topics and services

## Mode keys

```text
1 AUTO | 2 MANUAL | 3 ROS | E emergency stop + MANUAL
```

## Manual gesture keys

```text
N NOD | O SUNGLASSES_NOD | G SIGMA_NOD
X SHAKE | B LOOK_AROUND | M CELEBRATE
Z SLEEP | W WAKE_UP | 0 CANCEL
4 SIGMA face | 5 SUNGLASSES face
```

Manual repeat count and face-lock time are configured in
`robot_head_project/config.py`:

```python
MANUAL_GESTURE_COUNT = 2
MANUAL_FACE_HOLD_MS = 4000
```

## High-level API

```python
robot_head.show_face("SIGMA", hold_ms=4000)
robot_head.nod_head(count=2)
robot_head.sunglasses_nod(count=2, hold_ms=4000)
robot_head.sigma_nod(count=3, hold_ms=5000)
robot_head.shake_head(count=2)
robot_head.look_around(count=1)
robot_head.celebrate(count=2, hold_ms=4000)
robot_head.sleep(hold_ms=5000)
robot_head.wake_up(hold_ms=3000)
robot_head.cancel_gesture()
```

Movement sequencing is performed on the RP2350. During an active gesture,
incoming head-pose commands are ignored until the gesture completes or is
cancelled. The intentional `NEUTRAL -> CURIOUS` mapping is preserved.
