# Control Modes and Manual Keys

Only one source has command authority at a time:

```text
1 -> AUTO
2 -> MANUAL
3 -> ROS
E -> emergency stop + MANUAL
```

## Manual keys

Click inside the OpenCV window before pressing keys.

```text
J/L pan             I/K tilt
C center             S stop
A arm wave           F curious
4 sigma face         5 sunglasses face

N nod                O sunglasses nod
G sigma nod          X shake
B look around        M celebrate
6 dance              7 greet
8 daisy dance        0 cancel gesture
Z sleep              W wake up
```

## Manual parameter source

`robot_head_project/config.py`:

```python
MANUAL_GESTURE_COUNT = 2
MANUAL_FACE_HOLD_MS = 4000
```

`MANUAL_GESTURE_COUNT` means:

- `DANCE`: full right-centre-left-centre cycles.
- `GREET`: nods on each side.
- `DAISY_DANCE`: full head-and-arm dance cycles.

The RP2350 runs the complete choreography. Tracking pose commands are ignored
until the active movement completes or `0`, `STOP` or `CENTER` cancels it.
