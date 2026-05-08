import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_dir = Path(get_package_share_directory("lng_terminal_world"))
    world_file = str(pkg_dir / "worlds" / "lng_terminal.sdf")

    # Gazebo Sim (Ignition) server + GUI
    gz_sim = ExecuteProcess(
        cmd=["gz", "sim", "-r", "-v4", world_file],
        output="screen",
    )

    # Bridge camera topics from Gazebo to ROS2
    # /camera drones and CCTV publish to gz topic; we bridge to ROS2
    bridge_cctv = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="cctv_bridge",
        arguments=[
            "/cctv_gate/body/cctv_cam/image@sensor_msgs/Image[gz.msgs.Image",
        ],
        output="screen",
        remappings=[("/cctv_gate/body/cctv_cam/image", "/cctv_gate/image_raw")],
    )

    bridge_drone = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="drone_bridge",
        arguments=[
            "/drone/base_link/drone_cam/image@sensor_msgs/Image[gz.msgs.Image",
        ],
        output="screen",
        remappings=[("/drone/base_link/drone_cam/image", "/drone_cam/image_raw")],
    )

    return LaunchDescription([
        gz_sim,
        bridge_cctv,
        bridge_drone,
    ])
