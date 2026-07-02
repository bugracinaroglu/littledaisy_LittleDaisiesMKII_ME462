# Changes V15 — ROS2 Docker Ready

- Added a local JSON-lines command server to the Raspberry Pi OS application.
- The Pi host remains the only owner of Picamera2, OpenCV and RP2350 serial.
- Added a complete `ament_python` ROS2 package under `ros2_ws/src/robot_head_ros`.
- Added reconnecting Docker-to-host bridge client.
- Added command topics, Trigger services and status publishers.
- Added ROS/AUTO/MANUAL mode services.
- Added emergency-stop topic and service.
- Added `compose.ros2.yaml` with mandatory `network_mode: host`.
- Added optional Fast DDS Discovery Server compose override.
- Added Dockerfile based on configurable ROS distribution, default Jazzy.
- Added environment-based host settings and ROS bridge settings.
- Added serial-write and control-mode thread safety.
- Added Turkish Docker/ROS2 setup and troubleshooting guide.
