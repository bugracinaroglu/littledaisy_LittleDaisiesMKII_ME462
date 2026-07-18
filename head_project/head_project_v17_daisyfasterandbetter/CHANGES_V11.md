# Changes in v11

- Added RP2350 `POSE` gesture steps so pan and tilt can move simultaneously.
- Added `DANCE` with `SUNGLASSES` face.
- Added `GREET` with side-specific nods and `SUNGLASSES` face.
- Added `DAISY_DANCE` with head choreography and finite two-arm rhythm.
- Added configuration constants for dance, greeting and arm rhythm.
- Added Raspberry Pi API methods: `dance`, `greet`, `daisy_dance`.
- Added MANUAL keys: `6`, `7`, `8`.
- Added ROS2 Trigger services for all three movements.
- Updated serial parser, supported gesture lists and documentation.
- Preserved reduced RUNNING sensitivity and `NEUTRAL -> CURIOUS` behavior.
