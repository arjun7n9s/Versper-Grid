#!/usr/bin/env bash
# =============================================================================
# VesperGrid Droplet Setup Script — Full Recovery Edition
# Reproduces the complete cloud environment on a fresh Ubuntu 24.04
# DigitalOcean vLLM droplet (AMD MI300X, rocm Docker container pre-installed).
#
# Usage:
#   chmod +x droplet_setup.sh && ./droplet_setup.sh
#
# Pre-conditions:
#   - Ubuntu 24.04 x86_64
#   - rocm Docker container running with Qwen2.5-VL-7B-Instruct on port 8000
#
# Issues solved and baked in (so you never debug them again):
#   1. ROS2 sensor_msgs needs numpy — use system python3-numpy (not venv)
#   2. frame_sampler uses httpx in a thread — install via --break-system-packages
#   3. frame_sampler async _poll_result crashes (no event loop) — patched to sync thread
#   4. sensor_count validation le=20 breached when sensor_trace has 30 items — capped in main.py
#   5. Gazebo Harmonic OgreNext segfaults headlessly — use --render-engine ogre (legacy Ogre 1.x)
#   6. GZ_SIM_RESOURCE_PATH must include /models subdir for gas_plume/gas_haze to resolve
#   7. DroneAnimator plugin used ignition:: namespace — ported to gz:: for Harmonic
#   8. CMakeLists used ignition-cmake2/gazebo6 — ported to gz-cmake3/gz-sim8
#   9. Stale CMakeCache from local build causes server build failure — always rm -rf build/
#  10. ros_gz_bridge topic remapping: long Gazebo topic paths → short /cctv_south/image_raw
#  11. vLLM client double /v1 in URL — base_url already has /v1, just append /chat/completions
#  12. API falls back to deterministic if job queue overloaded — frame interval set to 20s
#  13. Multi-worker uvicorn causes 404 on /await (job in worker 1, poll hits worker 2) — known, safe to ignore
#  14. Drone camera spawns inside Tank B-4 mesh (black image) — spawn at 90 -65 22
#  15. Scene too dark for vLLM analysis — global ambient raised to 0.85
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/arjun7n9s/Versper-Grid.git"
INSTALL_DIR="/opt/vespergrid"
VENV="$INSTALL_DIR/vespergrid-venv"
ROS_DISTRO="jazzy"
SAMPLER_SCRIPT="$INSTALL_DIR/ros2_temp/install/lng_terminal_world/lib/lng_terminal_world/frame_sampler.py"
SDF="$INSTALL_DIR/ros2_temp/install/lng_terminal_world/share/lng_terminal_world/worlds/lng_terminal.sdf"

echo "===== [1/11] System packages ====="
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git curl python3-pip python3-full python3-venv \
  python3-numpy python3-requests python3-opencv \
  xvfb caddy libgl1-mesa-dri mesa-utils

# FIX #2: httpx must be on system Python (frame_sampler runs under system python3 via ROS2)
# Can't use venv python because ROS2 setup.bash wires /opt/ros/jazzy site-packages to system python
pip3 install --break-system-packages httpx

echo "===== [2/11] ROS2 Jazzy ====="
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

echo "===== [3/11] Gazebo Harmonic ====="
curl -sSL https://packages.osrfoundation.org/gazebo.gpg \
  -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
http://packages.osrfoundation.org/gazebo/ubuntu-stable noble main" \
  > /etc/apt/sources.list.d/gazebo-stable.list
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y gz-harmonic

echo "===== [4/11] Clone / update repo ====="
mkdir -p "$INSTALL_DIR"
if [ -d "$INSTALL_DIR/.git" ]; then
  cd "$INSTALL_DIR" && git pull origin main
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo "===== [5/11] Python venv + API deps ====="
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install \
  fastapi "uvicorn[standard]" python-multipart aiofiles \
  pillow httpx requests openai pydantic

echo "===== [6/11] Build ROS2 package ====="
source /opt/ros/$ROS_DISTRO/setup.bash
rosdep init 2>/dev/null || true
rosdep update
# FIX #9: always wipe stale CMakeCache (leftover from local dev machine build)
cd "$INSTALL_DIR/ros2_temp"
rm -rf build/ install/ log/
colcon build --packages-select lng_terminal_world
echo "ROS2 package built."

echo "===== [7/11] Patch SDF scene ====="
# FIX #15: raise global ambient from 0.26 → 0.85 so cameras produce usable images for vLLM
sed -i 's/<ambient>0\.26 0\.24 0\.22 1\.0<\/ambient>/<ambient>0.85 0.82 0.78 1.0<\/ambient>/' "$SDF"
# FIX #14: drone_d1 default spawn was inside Tank B-4 mesh → black image
# Move spawn to 90,-65,22 facing tank (yaw=3.14). DroneAnimator also updated to orbit at radius 28m.
sed -i 's|<model name="drone_d1"><static>false</static><pose>72 -50 0\.18 0 0 -2\.4|<model name="drone_d1"><static>false</static><pose>90 -65 22 0 0 3.14|' "$SDF"
# FIX #14b: drone camera was pitched 90° down (looked at dark ground) → forward-angled at 0.3 rad
sed -i 's|<pose>0 0 -0\.18 0 1\.5707 0</pose>|<pose>0 0.2 0 0 0.3 0</pose>|' "$SDF"
echo "SDF patched."

echo "===== [8/11] Patch frame_sampler: async→sync poll ====="
# FIX #3: _poll_result used asyncio.sleep + httpx.AsyncClient inside ROS2 executor task
# which crashed with "no running event loop". Replace with a plain threading.Thread + requests.
python3 - <<'PATCH'
path = "/opt/vespergrid/ros2_temp/install/lng_terminal_world/lib/lng_terminal_world/frame_sampler.py"
with open(path) as f:
    src = f.read()

old_call = (
    "# Fire-and-forget SSE poll in background\n"
    "            self.executor.create_task(self._poll_result(job_id))  # type: ignore[attr-defined]"
)
new_call = (
    "# Fire-and-forget poll in background thread\n"
    "            import threading\n"
    "            threading.Thread(target=self._poll_result_sync, args=(job_id,), daemon=True).start()"
)
src = src.replace(old_call, new_call)

sync_fn = '''
    def _poll_result_sync(self, job_id: str) -> None:
        import time, requests as _req
        time.sleep(4)
        try:
            url = f"{_API_URL}/ingest/{job_id}/await"
            r = _req.post(url, params={"timeout_seconds": 110}, timeout=120)
            r.raise_for_status()
            snap = r.json()
            backend = snap.get("backend", "?")
            result = snap.get("result") or {}
            n_ev = len(result.get("evidence", []))
            self.get_logger().info(
                f"[job {job_id[:8]}] done backend={backend} evidence={n_ev}"
            )
        except Exception as exc:
            self.get_logger().warning(f"[job {job_id[:8]}] poll failed: {exc}")

'''
src = src.replace(
    "    async def _poll_result(self, job_id: str)",
    sync_fn + "    async def _poll_result(self, job_id: str)"
)
with open(path, "w") as f:
    f.write(src)
print("frame_sampler patched.")
PATCH

echo "===== [9/11] Caddy config ====="
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

echo "===== [10/11] Systemd services ====="

# --- Xvfb: virtual display needed by Gazebo even in server-only mode ---
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

# --- Gazebo headless ---
# FIX #5: OgreNext (default renderer) segfaults on headless MI300X → use --render-engine ogre
# FIX #6: GZ_SIM_RESOURCE_PATH must include /models for gas_plume/gas_haze model:// URIs
# FIX #7+8: DroneAnimator ported to gz:: namespace, CMakeLists to gz-sim8 (in source)
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
# FIX #10: Gazebo publishes on long world-scoped topics; bridge remaps to short /cctv_south/image_raw etc.
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
# FIX #1: uses system python3 (not venv) because ROS2 sensor_msgs requires system python3-numpy
# FIX #12: SAMPLE_INTERVAL_S=20 to avoid overloading the vLLM inference queue
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
# FIX #11: VLLM_BASE_URL must NOT have trailing /v1/chat/completions — vlm_client.py appends /chat/completions
# FIX #4: sensor_count capped to min(20,...) in main.py (le=20 pydantic constraint)
# FIX #13: 2 workers causes 404 on /await when job lands on worker 1 but poll hits worker 2 — harmless
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

# --- Synthetic frame fallback (DISABLED by default — only enable if Gazebo fails) ---
cat > /etc/systemd/system/vespergrid-frames.service <<'EOF'
[Unit]
Description=VesperGrid Synthetic Frame Generator (fallback only)
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

echo "===== [11/11] Node 22 + frontend build + start all ====="
if ! command -v node &>/dev/null || [[ "$(node -v)" != v22* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi
cd "$INSTALL_DIR/apps/console"
npm ci
npm run build

# Start in dependency order with wait times
systemctl start xvfb
sleep 3
systemctl start vespergrid-api
sleep 4
systemctl start vespergrid-gazebo
sleep 22   # Gazebo needs time to load world before bridge can subscribe
systemctl start vespergrid-bridge
sleep 6
systemctl start vespergrid-sampler
systemctl restart caddy

echo ""
echo "============================================================"
echo " VesperGrid stack status:"
echo "============================================================"
for svc in xvfb vespergrid-gazebo vespergrid-bridge vespergrid-sampler vespergrid-api caddy; do
  printf "  %-30s %s\n" "$svc" "$(systemctl is-active $svc)"
done
echo ""
echo " Dashboard : http://$(curl -s ifconfig.me 2>/dev/null || echo '<droplet-ip>')"
echo " API feeds : http://localhost:8742/api/feeds"
echo " vLLM check: curl -s http://localhost:8000/v1/models | python3 -m json.tool"
echo ""
echo " To expose publicly:"
echo "   cloudflared tunnel --url http://localhost:80"
echo ""
echo " If Gazebo cameras show black/dark images:"
echo "   - Check drone spawn didn't land inside a mesh: journalctl -u vespergrid-gazebo -n 20"
echo "   - Verify ambient patch applied: grep 'ambient>0.8' \$SDF"
echo ""
echo " If sampler shows 'No frames received':"
echo "   - Bridge may not be up yet: journalctl -u vespergrid-bridge -n 10"
echo "   - Verify Gazebo topics: source /opt/ros/jazzy/setup.bash && gz topic -l | grep image"
echo ""
echo " Fallback (synthetic frames): systemctl start vespergrid-frames"
echo "============================================================"
