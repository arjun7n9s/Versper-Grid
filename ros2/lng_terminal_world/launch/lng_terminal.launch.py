import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_dir = Path(get_package_share_directory("lng_terminal_world"))
    world_file = str(pkg_dir / "worlds" / "lng_terminal.sdf")

    # Force Ogre2 (OGRE-Next) for PBR materials, shadows, particles, sky
    set_render_engine = SetEnvironmentVariable(
        name="GZ_SIM_RENDER_ENGINE_SERVER_API_BACKEND",
        value="ogre2",
    )
    set_render_engine_gui = SetEnvironmentVariable(
        name="GZ_SIM_RENDER_ENGINE_GUI_API_BACKEND",
        value="ogre2",
    )
    # Allow software (llvmpipe) fallback when no discrete GPU is present
    set_mesa_gl = SetEnvironmentVariable(
        name="MESA_GL_VERSION_OVERRIDE",
        value="4.5",
    )
    set_libgl = SetEnvironmentVariable(
        name="LIBGL_ALWAYS_SOFTWARE",
        value="0",
    )

    # Ignition Fortress: use 'ign gazebo' (Harmonic uses 'gz sim')
    gz_sim = ExecuteProcess(
        cmd=["ign", "gazebo", "-r", "-v4", "--render-engine", "ogre2", world_file],
        output="screen",
    )

    # Bridge camera topics from Gazebo to ROS2
    # /camera drones and CCTV publish to gz topic; we bridge to ROS2
    bridge_cctv = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="cctv_bridge",
        arguments=[
            "/cctv_gate/body/cctv_cam/image@sensor_msgs/msg/Image[ignition.msgs.Image",
        ],
        output="screen",
        remappings=[("/cctv_gate/body/cctv_cam/image", "/cctv_gate/image_raw")],
    )

    bridge_drone = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="drone_bridge",
        arguments=[
            "/drone/base_link/drone_cam/image@sensor_msgs/msg/Image[ignition.msgs.Image",
        ],
        output="screen",
        remappings=[("/drone/base_link/drone_cam/image", "/drone_cam/image_raw")],
    )

    return LaunchDescription([
        set_render_engine,
        set_render_engine_gui,
        set_mesa_gl,
        set_libgl,
        gz_sim,
        bridge_cctv,
        bridge_drone,
    ])
