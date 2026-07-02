# Raspberry Pi Gesture API

The implementation is `RobotHeadInterface` in `robot_head_interface.py`.

```python
robot_head.show_face("SIGMA", hold_ms=4000)
robot_head.nod_head(count=2)
robot_head.sunglasses_nod(count=2, hold_ms=4000)
robot_head.sigma_nod(count=2, hold_ms=4000)
robot_head.shake_head(count=2)
robot_head.look_around(count=1)
robot_head.celebrate(count=2, hold_ms=4000)
robot_head.sleep(hold_ms=5000)
robot_head.wake_up(hold_ms=3000)
robot_head.cancel_gesture()
```

`count` is clamped by `MAX_GESTURE_COUNT`. `hold_ms` is sent to the RP2350 and
temporarily prevents IMU face overrides. The default command source is MANUAL;
AUTO and ROS code must pass `source=ControlMode.AUTO` or
`source=ControlMode.ROS`.
