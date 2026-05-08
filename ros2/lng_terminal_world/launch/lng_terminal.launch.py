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
    # Tell Gazebo where to find our custom system plugins (DroneAnimator.so).
    # ament installs them to share/<pkg>/../../lib/<pkg>/
    plugin_dir = str(pkg_dir.parent.parent / "lib" / "lng_terminal_world")
    set_plugin_path = SetEnvironmentVariable(
        name="IGN_GAZEBO_SYSTEM_PLUGIN_PATH",
        value=plugin_dir + ":" + os.environ.get("IGN_GAZEBO_SYSTEM_PLUGIN_PATH", ""),
    )

    # Ignition Fortress: use 'ign gazebo' (Harmonic uses 'gz sim')
    gz_sim = ExecuteProcess(
        cmd=["ign", "gazebo", "-r", "-v4", "--render-engine", "ogre2", world_file],
        output="screen",
    )

    # ── Camera bridge nodes ──────────────────────────────────────────────────
    # Ignition publishes on /world/<world>/model/<m>/link/<l>/sensor/<s>/image
    # ros_gz_bridge needs the full ign path; we remap to clean ROS2 topic names.
    W = "lng_terminal"
    IMG = "@sensor_msgs/msg/Image[ignition.msgs.Image"
    CAM_INFO = "@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo"

    def _ign(model, link, sensor, suffix):
        return f"/world/{W}/model/{model}/link/{link}/sensor/{sensor}/{suffix}"

    bridge_cctv_gate = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="bridge_cctv_gate",
        arguments=[
            f"{_ign('cctv_gate',  'cam_sensor_link', 'cctv_gate_cam',  'image')}{IMG}",
            f"{_ign('cctv_gate',  'cam_sensor_link', 'cctv_gate_cam',  'camera_info')}{CAM_INFO}",
        ],
        remappings=[
            (_ign("cctv_gate", "cam_sensor_link", "cctv_gate_cam", "image"),       "/cctv_gate/image_raw"),
            (_ign("cctv_gate", "cam_sensor_link", "cctv_gate_cam", "camera_info"), "/cctv_gate/camera_info"),
        ],
        output="screen",
    )

    bridge_cctv_south = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="bridge_cctv_south",
        arguments=[
            f"{_ign('cctv_south', 'cam_sensor_link', 'cctv_south_cam', 'image')}{IMG}",
            f"{_ign('cctv_south', 'cam_sensor_link', 'cctv_south_cam', 'camera_info')}{CAM_INFO}",
        ],
        remappings=[
            (_ign("cctv_south", "cam_sensor_link", "cctv_south_cam", "image"),       "/cctv_south/image_raw"),
            (_ign("cctv_south", "cam_sensor_link", "cctv_south_cam", "camera_info"), "/cctv_south/camera_info"),
        ],
        output="screen",
    )

    bridge_drone = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="bridge_drone_d1",
        arguments=[
            f"{_ign('drone_d1', 'base_link', 'drone_cam', 'image')}{IMG}",
            f"{_ign('drone_d1', 'base_link', 'drone_cam', 'camera_info')}{CAM_INFO}",
        ],
        remappings=[
            (_ign("drone_d1", "base_link", "drone_cam", "image"),       "/drone_d1/image_raw"),
            (_ign("drone_d1", "base_link", "drone_cam", "camera_info"), "/drone_d1/camera_info"),
        ],
        output="screen",
    )

    # Drone animation is handled by the C++ DroneAnimator system plugin
    # loaded directly by Gazebo (see worlds/lng_terminal.sdf). Runs at 1 kHz
    # inside the sim loop — zero subprocess/network overhead.

    return LaunchDescription([
        set_render_engine,
        set_render_engine_gui,
        set_mesa_gl,
        set_libgl,
        set_plugin_path,
        gz_sim,
        bridge_cctv_gate,
        bridge_cctv_south,
        bridge_drone,
    ])
