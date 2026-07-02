import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory("robot_head_ros")
    config_file = os.path.join(package_share, "config", "robot_head.yaml")

    environment_overrides = {
        "bridge_host": os.getenv("ROBOT_HEAD_BRIDGE_HOST", "127.0.0.1"),
        "bridge_port": int(os.getenv("ROBOT_HEAD_BRIDGE_PORT", "8765")),
        "auto_switch_to_ros": os.getenv(
            "ROBOT_HEAD_AUTO_SWITCH_TO_ROS",
            "true",
        ).strip().lower() in ("1", "true", "yes", "on"),
    }

    return LaunchDescription(
        [
            Node(
                package="robot_head_ros",
                executable="robot_head_node",
                name="robot_head_ros_bridge",
                output="screen",
                parameters=[config_file, environment_overrides],
            )
        ]
    )
