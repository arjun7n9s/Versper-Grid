from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("api_url", default_value="http://localhost:8742"),
        DeclareLaunchArgument("location", default_value="LNG Terminal Alpha, Chennai Corridor"),
        DeclareLaunchArgument("auto_trigger", default_value="true"),
        DeclareLaunchArgument("threshold_ppm", default_value="15.0"),
        DeclareLaunchArgument("frames_per_cam", default_value="3"),
        Node(
            package="evidence_bridge",
            executable="bridge_node",
            name="evidence_bridge",
            output="screen",
            parameters=[{
                "api_url": LaunchConfiguration("api_url"),
                "location": LaunchConfiguration("location"),
                "auto_trigger": LaunchConfiguration("auto_trigger"),
                "threshold_ppm": LaunchConfiguration("threshold_ppm"),
                "frames_per_cam": LaunchConfiguration("frames_per_cam"),
            }],
        ),
    ])
