ARG ROS_DISTRO=jazzy
FROM ros:${ROS_DISTRO}-ros-base

ARG ROS_DISTRO
ENV ROS_DISTRO=${ROS_DISTRO}
ENV DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions \
    iproute2 \
    iputils-ping \
    net-tools \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws
COPY ros2_ws/src /ros2_ws/src

RUN source /opt/ros/${ROS_DISTRO}/setup.bash \
    && colcon build --symlink-install

COPY docker/ros2/entrypoint.sh /ros_entrypoint_custom.sh
RUN chmod +x /ros_entrypoint_custom.sh

ENTRYPOINT ["/ros_entrypoint_custom.sh"]
CMD ["ros2", "launch", "robot_head_ros", "robot_head.launch.py"]
