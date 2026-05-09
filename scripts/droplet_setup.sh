#!/usr/bin/env bash
# =============================================================================
# VesperGrid Droplet Setup Script
# Reproduces the full cloud environment from scratch on a fresh Ubuntu 24.04
# DigitalOcean vLLM droplet (AMD MI300X, rocm Docker container pre-installed).
#
# Usage:
#   chmod +x droplet_setup.sh
#   ./droplet_setup.sh
#
# Expected pre-conditions:
#   - Ubuntu 24.04 x86_64
#   - Docker installed with rocm container running (vLLM droplet 1-click)
#   - Git repo cloned or accessible
#   - SSH key present for GitHub access
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/arjun7n9s/Versper-Grid.git"
INSTALL_DIR="/opt/vespergrid"
VENV="$INSTALL_DIR/vespergrid-venv"
ROS_DISTRO="jazzy"

echo "===== [1/10] System packages ====="
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git curl python3-pip python3-full python3-venv \
  python3-numpy python3-requests python3-opencv \
  xvfb caddy

# Install httpx for system Python (used by frame_sampler poll thread)
pip3 install --break-system-packages httpx

echo "===== [2/10] ROS2 Jazzy ====="
curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc \
  | gpg --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu noble main" \
  > /etc/apt/sources.list.d/ros2.list
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ros-jazzy-ros-base \
  ros-jazzy-vision-msgs \
  ros-jazzy-sensor-msgs \
  ros-jazzy-cv-bridge \
  ros-jazzy-ros-gz \
  python3-rosdep \
  python3-colcon-common-extensions

echo "===== [3/10] Gazebo Harmonic ====="
curl -sSL https://packages.osrfoundation.org/gazebo.gpg \
  -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
  http://packages.osrfoundation.org/gazebo/ubuntu-stable noble main" \
  > /etc/apt/sources.list.d/gazebo-stable.list
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y gz-harmonic
# Mesa software renderer (needed for headless rendering without physical GPU access)
apt-get install -y libgl1-mesa-dri mesa-utils

echo "===== [4/10] Clone repo ====="
mkdir -p "$INSTALL_DIR"
if [ -d "$INSTALL_DIR/.git" ]; then
  cd "$INSTALL_DIR" && git pull origin main
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo "===== [5/10] Python venv + API deps ====="
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install \
  fastapi uvicorn[standard] python-multipart aiofiles \
  pillow httpx requests openai pydantic

echo "===== [6/10] Build ROS2 package ====="
source /opt/ros/$ROS_DISTRO/setup.bash
rosdep init 2>/dev/null || true
rosdep update
cd "$INSTALL_DIR/ros2_temp"
rm -rf build/ install/ log/
colcon build --packages-select lng_terminal_world
echo "ROS2 package built."

echo "===== [7/10] Fix scene: ambient light + drone cam ====="
SDF="$INSTALL_DIR/ros2_temp/install/lng_terminal_world/share/lng_terminal_world/worlds/lng_terminal.sdf"
# Increase global ambient to 0.85 for camera clarity
sed -i 's/<ambient>0\.26 0\.24 0\.22 1\.0<\/ambient>/<ambient>0.85 0.82 0.78 1.0<\/ambient>/' "$SDF"
# Move drone spawn away from Tank B-4
sed -i 's/<model name="drone_d1"><static>false<\/static><pose>72 -50 0\.18/<model name="drone_d1"><static>false<\/static><pose>90 -65 22/' "$SDF"
echo "SDF patched."

echo "===== [8/10] Caddy config ====="
cat > /etc/caddy/Caddyfile <<'EOF'
:80 {
    handle /api/* {
        reverse_proxy localhost:8742
    }
    handle {
        root * /opt/vespergrid/apps/console/dist
        file_server
        try_files {path} /index.html
    }
}
EOF
systemctl enable caddy
systemctl restart caddy

echo "===== [9/10] Systemd services ====="

# --- Xvfb (virtual display for headless Gazebo) ---
cat > /etc/systemd/system/xvfb.service <<'EOF'
[Unit]
Description=Virtual Frame Buffer
After=network.target

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# --- Gazebo headless simulation ---
cat > /etc/systemd/system/vespergrid-gazebo.service <<'EOF'
[Unit]
Description=VesperGrid Gazebo Simulation (headless)
After=xvfb.service
Requires=xvfb.service

[Service]
User=root
Environment=DISPLAY=:99
Environment=LIBGL_ALWAYS_SOFTWARE=1
Environment=MESA_GL_VERSION_OVERRIDE=3.3
Environment=GALLIUM_DRIVER=softpipe
Environment=GZ_SIM_RESOURCE_PATH=/opt/vespergrid/ros2_temp/install/lng_terminal_world/share/lng_terminal_world:/opt/vespergrid/ros2_temp/install/lng_terminal_world/share/lng_terminal_world/models
Environment=GZ_SIM_SYSTEM_PLUGIN_PATH=/opt/vespergrid/ros2_temp/install/lng_terminal_world/lib/lng_terminal_world
ExecStart=/bin/bash -c 'source /opt/ros/jazzy/setup.bash && source /opt/vespergrid/ros2_temp/install/setup.bash && gz sim -r -s --render-engine ogre --headless-rendering /opt/vespergrid/ros2_temp/install/lng_terminal_world/share/lng_terminal_world/worlds/lng_terminal.sdf'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# --- ROS-Gazebo image bridge ---
cat > /etc/systemd/system/vespergrid-bridge.service <<'EOF'
[Unit]
Description=VesperGrid ROS-Gazebo Image Bridge
After=vespergrid-gazebo.service
Requires=vespergrid-gazebo.service

[Service]
User=root
Environment=DISPLAY=:99
ExecStart=/bin/bash -c 'source /opt/ros/jazzy/setup.bash && source /opt/vespergrid/ros2_temp/install/setup.bash && ros2 run ros_gz_bridge parameter_bridge \
  /world/lng_terminal/model/cctv_south/link/cam_sensor_link/sensor/cctv_south_cam/image@sensor_msgs/msg/Image[gz.msgs.Image \
  /world/lng_terminal/model/drone_d1/link/base_link/sensor/drone_cam/image@sensor_msgs/msg/Image[gz.msgs.Image \
  /world/lng_terminal/model/cctv_gate/link/cam_sensor_link/sensor/cctv_gate_cam/image@sensor_msgs/msg/Image[gz.msgs.Image \
  --ros-args \
    -r /world/lng_terminal/model/cctv_south/link/cam_sensor_link/sensor/cctv_south_cam/image:=/cctv_south/image_raw \
    -r /world/lng_terminal/model/drone_d1/link/base_link/sensor/drone_cam/image:=/drone_d1/image_raw \
    -r /world/lng_terminal/model/cctv_gate/link/cam_sensor_link/sensor/cctv_gate_cam/image:=/cctv_gate/image_raw'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# --- Frame sampler (ROS2 → API) ---
cat > /etc/systemd/system/vespergrid-sampler.service <<'EOF'
[Unit]
Description=VesperGrid ROS2 Frame Sampler
After=vespergrid-bridge.service vespergrid-api.service
Requires=vespergrid-bridge.service

[Service]
User=root
Environment=DISPLAY=:99
Environment=VESPER_API_URL=http://localhost:8742/api
Environment=SAMPLE_INTERVAL_S=20
Environment=MAX_FRAMES_PER_BUNDLE=3
Environment=JPEG_QUALITY=85
ExecStart=/bin/bash -c 'source /opt/ros/jazzy/setup.bash && source /opt/vespergrid/ros2_temp/install/setup.bash && /usr/bin/python3 /opt/vespergrid/ros2_temp/install/lng_terminal_world/lib/lng_terminal_world/frame_sampler.py'
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF

# --- FastAPI backend ---
cat > /etc/systemd/system/vespergrid-api.service <<'EOF'
[Unit]
Description=VesperGrid FastAPI Backend
After=network.target

[Service]
User=root
WorkingDirectory=/opt/vespergrid/apps/api
Environment=PYTHONUNBUFFERED=1
Environment=VLLM_BASE_URL=http://localhost:8000/v1
Environment=VLLM_MODEL=/shared-docker/Qwen2.5-VL-7B-Instruct
ExecStart=/opt/vespergrid/vespergrid-venv/bin/uvicorn vespergrid.main:app --host 0.0.0.0 --port 8742 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# --- Synthetic frame fallback (keep disabled by default, enable if Gazebo fails) ---
cat > /etc/systemd/system/vespergrid-frames.service <<'EOF'
[Unit]
Description=VesperGrid Synthetic Frame Generator (fallback)
After=vespergrid-api.service

[Service]
User=root
Environment=VESPER_API_URL=http://localhost:8742/api
ExecStart=/opt/vespergrid/vespergrid-venv/bin/python3 /opt/vespergrid/scripts/gen_frames.py
Restart=always
RestartSec=20

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xvfb vespergrid-gazebo vespergrid-bridge vespergrid-sampler vespergrid-api

echo "===== [10/10] Build frontend + start all services ====="
cd "$INSTALL_DIR/apps/console"
# Install Node 22 if missing
if ! command -v node &>/dev/null || [[ "$(node -v)" != v22* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi
npm ci
npm run build

# Start services in order
systemctl start xvfb
sleep 3
systemctl start vespergrid-api
sleep 3
systemctl start vespergrid-gazebo
sleep 20
systemctl start vespergrid-bridge
sleep 5
systemctl start vespergrid-sampler
systemctl restart caddy

echo ""
echo "=============================================="
echo " VesperGrid stack is up. Service statuses:"
echo "=============================================="
for svc in xvfb vespergrid-gazebo vespergrid-bridge vespergrid-sampler vespergrid-api caddy; do
  printf "  %-28s %s\n" "$svc" "$(systemctl is-active $svc)"
done
echo ""
echo " Dashboard:  http://$(curl -s ifconfig.me)"
echo " API:        http://localhost:8742/api/feeds"
echo " vLLM:       http://localhost:8000/v1/models"
echo ""
echo " To expose publicly: cloudflared tunnel --url http://localhost:80"
echo "=============================================="
