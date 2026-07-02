# ROS2 workspace

The `robot_head_ros` package is built inside the Docker image.

Manual native build on a ROS2 Jazzy machine:

```bash
cd ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 launch robot_head_ros robot_head.launch.py
```

For Raspberry Pi OS, use the project-root `compose.ros2.yaml` instead.
