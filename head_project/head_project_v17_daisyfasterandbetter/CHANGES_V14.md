# Changes V14 — LCD Text and Thinking Face

This version is based on the user's V13 project and keeps all V13 servo limits,
smooth motion settings, centered gestures, faces, dances, and control modes.

## Added

- `THINKING` animated face.
- Temporary full-screen LCD text overlay.
- Software-sheared italic text rendering.
- High-level `show_text(...)` function.
- High-level `show_oopsie_daisy(...)` function.
- ROS2 `/robot_head/text` topic.
- ROS2 `oopsie_daisy` and `thinking` topics/services.
- MANUAL keyboard controls for all three features.

## Serial commands

```text
FACE:THINKING,4000
TEXT:5000,1,Oopsie Daisy
TEXT:4000,0,Hello Daisy
```

`TEXT` format:

```text
TEXT:hold_ms,italic,text
```

- `hold_ms=0`: keep the text visible until another face, gesture, or center
  command replaces it.
- `italic=1`: software italic.
- `italic=0`: normal text.
- Text is restricted to a single serial line and the first 80 characters.

## Manual keys

```text
9  -> THINKING face
[  -> italic "Oopsie Daisy"
]  -> configured general text
```
