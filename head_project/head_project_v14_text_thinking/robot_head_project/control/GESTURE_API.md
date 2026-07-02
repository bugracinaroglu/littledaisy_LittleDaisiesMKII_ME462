# Raspberry Pi Gesture API

Implementation:

```text
robot_head_project/control/robot_head_interface.py
```

## Faces

```python
robot_head.show_face("SIGMA", hold_ms=4000)
robot_head.show_face("SUNGLASSES", hold_ms=5000)
```

## Existing gestures

```python
robot_head.nod_head(count=3)
robot_head.sunglasses_nod(count=3, hold_ms=4000)
robot_head.sigma_nod(count=3, hold_ms=5000)
robot_head.shake_head(count=3)
robot_head.look_around(count=1, hold_ms=3000)
robot_head.celebrate(count=3, hold_ms=4000)
robot_head.sleep(hold_ms=5000)
robot_head.wake_up(hold_ms=3000)
```

## Dance and greeting

```python
robot_head.dance(count=3, hold_ms=7000)
robot_head.greet(nod_count=3, hold_ms=7000)
robot_head.daisy_dance(count=3, hold_ms=8000)
```

- `dance(count=3)`: three right-centre-left-centre head cycles.
- `greet(nod_count=3)`: two nods on the right and two on the left.
- `daisy_dance(count=3)`: three dance cycles plus two-arm rhythm.

All three automatically use the `SUNGLASSES` face.

## Cancelling

```python
robot_head.cancel_gesture()
robot_head.stop()
robot_head.center()
```

## Command source

The default source is `ControlMode.MANUAL`. For other modes:

```python
robot_head.dance(count=3, source=ControlMode.AUTO)
robot_head.greet(nod_count=3, source=ControlMode.ROS)
```

A command is rejected if its source does not match the active mode.


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
