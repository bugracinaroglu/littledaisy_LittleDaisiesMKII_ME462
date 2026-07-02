# Control Modes

The project now has one active command authority at a time.

- `AUTO`: camera tracking, emotion, gesture and RP2350 IMU behavior may control the robot.
- `MANUAL`: keyboard and direct Python API commands may control the robot. RP2350 IMU face/arm overrides are disabled.
- `ROS`: ROS2 topic/service commands may control the robot. RP2350 IMU face/arm overrides and the touch face test are disabled.

## Keyboard

- `1`: AUTO
- `2`: MANUAL
- `3`: ROS
- `E`: emergency stop and switch to MANUAL
- MANUAL only: `J/L` pan, `I/K` tilt, `C` center, `S` stop, `A` arm wave, `F` curious face

## Configuration

In `robot_head_project/config.py`:

```python
STARTUP_CONTROL_MODE = "AUTO"
ENABLE_ROS2_BRIDGE = False
```

Set `ENABLE_ROS2_BRIDGE = True` only in an environment where ROS2 Python packages are available.

## High-level Python API

`RobotHeadInterface` provides:

```python
robot_head.show_face("HAPPY")
robot_head.set_head_pose(110, 45)
robot_head.set_pan(110)
robot_head.set_tilt(45)
robot_head.center()
robot_head.stop()
robot_head.wave_arm()
```

The default source is `MANUAL`. AUTO and ROS callers explicitly pass their source, preventing different controllers from overwriting one another.

## ROS2 interfaces

Topics:

- `/robot_head/control_mode` — `std_msgs/String`
- `/robot_head/face` — `std_msgs/String`
- `/robot_head/pan` — `std_msgs/Float64`
- `/robot_head/tilt` — `std_msgs/Float64`
- `/robot_head/pose` — `std_msgs/Float64MultiArray` as `[pan, tilt]`
- `/robot_head/center`, `/robot_head/stop`, `/robot_head/arm_wave` — `std_msgs/Empty`

Services:

- `/robot_head/center_service` — `std_srvs/Trigger`
- `/robot_head/stop_service` — `std_srvs/Trigger`
- `/robot_head/arm_wave_service` — `std_srvs/Trigger`

The existing RP2350 behavior that converts an incoming `NEUTRAL` face command to `CURIOUS` is intentionally preserved.
