from glob import glob
from setuptools import find_packages, setup

package_name = "robot_head_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Little Daisy Team",
    maintainer_email="maintainer@example.com",
    description="ROS 2 to Raspberry Pi host bridge for the Little Daisy robot head.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "robot_head_node = robot_head_ros.robot_head_node:main",
        ],
    },
)
