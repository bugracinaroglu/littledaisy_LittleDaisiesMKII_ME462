# Robot Head ROS2 API

## Command topics

| Topic | Type | Payload |
|---|---|---|
| `/robot_head/control_mode` | `std_msgs/String` | `AUTO`, `MANUAL`, `ROS` |
| `/robot_head/face` | `std_msgs/String` | `FACE` or `FACE,hold_ms` |
| `/robot_head/text` | `std_msgs/String` | `text` or `hold_ms|italic|text` |
| `/robot_head/gesture` | `std_msgs/String` | `NAME[,count[,hold_ms]]` |
| `/robot_head/pan` | `std_msgs/Float64` | head pan angle |
| `/robot_head/tilt` | `std_msgs/Float64` | head tilt angle |
| `/robot_head/pose` | `std_msgs/Float64MultiArray` | `[pan, tilt]` |
| `/robot_head/center` | `std_msgs/Empty` | empty |
| `/robot_head/stop` | `std_msgs/Empty` | empty |
| `/robot_head/emergency_stop` | `std_msgs/Empty` | always accepted |
| `/robot_head/arm_wave` | `std_msgs/Empty` | empty |
| `/robot_head/cancel_gesture` | `std_msgs/Empty` | empty |
| `/robot_head/oopsie_daisy` | `std_msgs/Empty` | empty |
| `/robot_head/thinking` | `std_msgs/Empty` | empty |

## Status topics

| Topic | Type | Description |
|---|---|---|
| `/robot_head/status` | `std_msgs/String` | JSON status |
| `/robot_head/current_mode` | `std_msgs/String` | active authority |
| `/robot_head/bridge_connected` | `std_msgs/Bool` | Docker-to-host TCP bridge |
| `/robot_head/serial_connected` | `std_msgs/Bool` | Pi host-to-RP2350 serial |

## Trigger services

```text
/robot_head/auto_mode_service
/robot_head/manual_mode_service
/robot_head/ros_mode_service
/robot_head/center_service
/robot_head/stop_service
/robot_head/emergency_stop_service
/robot_head/arm_wave_service
/robot_head/nod_service
/robot_head/sunglasses_nod_service
/robot_head/sigma_nod_service
/robot_head/shake_service
/robot_head/look_around_service
/robot_head/celebrate_service
/robot_head/dance_service
/robot_head/greet_service
/robot_head/daisy_dance_service
/robot_head/sleep_service
/robot_head/wake_up_service
/robot_head/cancel_gesture_service
/robot_head/oopsie_daisy_service
/robot_head/thinking_service
```

## Supported faces

```text
NEUTRAL CURIOUS HAPPY SAD ANGRY SURPRISED DISGUST SLEEPING IDLE
RUNNING DIZZY SIGMA SUNGLASSES THINKING
```

`NEUTRAL` is intentionally rendered as `CURIOUS` by the RP2350.

## Supported gestures

```text
NOD SUNGLASSES_NOD SIGMA_NOD SHAKE LOOK_AROUND CELEBRATE
DANCE GREET DAISY_DANCE SLEEP WAKE_UP
```
