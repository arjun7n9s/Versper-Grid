# VesperGrid — Ubuntu / ROS2 Humble Runbook

Everything you need to run the full real pipeline on the Ubuntu dual-boot.

---

## 0. Verify your Gazebo version

```bash
gazebo --version          # Classic 11 → "Gazebo multi-robot simulator, version 11.x"
ign gazebo --version      # Harmonic/Fortress → "Ignition Gazebo, version X"
```

The canonical simulation now uses `ros2/lng_terminal_world/worlds/lng_terminal.sdf`
with Ignition/Gazebo Fortress-style bridges. The older `lng_terminal.world` is kept
only as a reference fallback.

---

## 1. Build the ROS2 workspace

```bash
cd ~/   # or wherever you want the workspace
mkdir -p vesper_ws/src && cd vesper_ws/src

# Copy the ros2/ folder from the repo here:
cp -r /path/to/AMD-S-2/ros2/lng_terminal_world .
cp -r /path/to/AMD-S-2/ros2/evidence_bridge .

cd ~/vesper_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

---

## 2. Install Python deps for the bridge

```bash
pip install requests opencv-python
```

---

## 3. Install VLM inference deps (RTX 5060)

```bash
# CUDA 12.x is required — verify first:
nvidia-smi

pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install transformers>=4.52.0 accelerate>=0.33.0 bitsandbytes>=0.43.0
pip install qwen-vl-utils pillow

# Test the GPU is visible:
python3 -c "import torch; print(torch.cuda.get_device_name(0))"
```

> **RTX 5060 note:** Blackwell (GB206) requires PyTorch >= 2.6 and CUDA 12.6+.
> If you hit a `no kernel image` error, upgrade torch:
> `pip install torch --pre --index-url https://download.pytorch.org/whl/nightly/cu128`

---

## 4. Install and start the FastAPI backend

```bash
cd /path/to/AMD-S-2
pip install -r apps/api/requirements.txt

# Set the GPU label so /api/health is honest:
export ACCELERATOR_LABEL="1x NVIDIA RTX 5060 (8GB VRAM) — local dev"

# Start the API:
npm run api
# OR directly:
uvicorn vespergrid.main:app --host 0.0.0.0 --port 8742 \
    --app-dir apps/api/src --reload
```

Verify:
```bash
curl -s http://localhost:8742/api/health | python3 -m json.tool
# vlm_backend should say "local_vlm" if CUDA is available
```

---

## 5. Launch Gazebo world

```bash
source ~/vesper_ws/install/setup.bash
ros2 launch lng_terminal_world lng_terminal.launch.py
```

Confirm camera topics are publishing:
```bash
ros2 topic list | grep image_raw
# /cctv_south/image_raw
# /drone_d1/image_raw
# /cctv_gate/image_raw
ros2 topic hz /drone_d1/image_raw   # should show ~5 Hz
```

---

## 6A. OPTION A — Record a ros2 bag (recommended for bag-replay demo)

```bash
# In a new terminal, start publishing the gas leak incident:
source ~/vesper_ws/install/setup.bash
ros2 run evidence_bridge gas_leak_publisher

# In another terminal, record all topics for 90 seconds:
ros2 bag record -o lng_incident_bag \
    /cctv_south/image_raw \
    /drone_d1/image_raw \
    /cctv_gate/image_raw \
    /gas_sensor_0/reading \
    /wind/state
# Let it run for ~90 seconds, then Ctrl+C
```

---

## 6B. OPTION B — Live run (no bag needed)

Skip recording; the bridge subscribes directly to live Gazebo topics.

---

## 7. Launch the Evidence Bridge

```bash
source ~/vesper_ws/install/setup.bash

# For live Gazebo:
ros2 launch evidence_bridge bridge.launch.py \
    api_url:=http://localhost:8742 \
    auto_trigger:=true \
    threshold_ppm:=15.0 \
    frames_per_cam:=3

# For bag replay (run this INSTEAD of live Gazebo):
ros2 bag play lng_incident_bag --loop &
ros2 run evidence_bridge gas_leak_publisher &
ros2 launch evidence_bridge bridge.launch.py \
    api_url:=http://localhost:8742
```

Watch for the trigger log:
```
[evidence_bridge]: Gas reading 18.4 ppm exceeds threshold 15.0 — auto-triggering ingest
[evidence_bridge]: Ingest job dispatched: job_id=abc123, images=6, backend=local_vlm
```

---

## 8. Watch it in the React console

```bash
# In another terminal:
npm --prefix /path/to/AMD-S-2/apps/console run dev
```

Open `http://localhost:5173` — when the bridge triggers, the console will show:
1. SSE progress bar advancing: queued → sampling → parsing → normalizing → synthesizing → complete
2. Real evidence items from Qwen-VL's observations
3. Deterministic gas/wind trend analysis from structured sensor traces
4. Voice reports as transcribed source-linked evidence when audio is uploaded
5. Source lineage: clicking an evidence row shows the actual Gazebo frame, transcript, or sensor trace summary

---

## 9. Manual trigger (for demo control)

You can trigger an ingest at any time without waiting for the gas threshold:

```bash
ros2 service call /vespergrid/trigger_ingest std_srvs/srv/Trigger {}
```

Or POST directly to the API with test images:
```bash
curl -X POST http://localhost:8742/api/ingest/upload \
  -F "images=@/path/to/frame.jpg" \
  -F "location=LNG Terminal Alpha" \
  -F "field_notes=Test ingest from curl"
```

---

## 10. Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'cv_bridge'` | `sudo apt install ros-humble-cv-bridge` |
| `libgazebo_ros_camera.so not found` | `sudo apt install ros-humble-gazebo-ros-pkgs` |
| `walk.dae not found` (actor skin) | Remove the `<actor>` block from the world or install `gazebo_models` |
| `torch.cuda not available` | Verify CUDA drivers: `nvidia-smi`, reinstall torch with correct CUDA wheel |
| `bitsandbytes CUDA error` | Set `VLM_LOAD_4BIT=0` in env to load in full BF16 (needs ~14GB VRAM) |
| Gas threshold never fires | Lower it: `threshold_ppm:=5.0` in the launch args |
| API returns `deterministic` backend | torch not imported properly; check API logs for import errors |

---

## 11. For the AMD Cloud demo (Phase 2)

When the MI300X is provisioned:
```bash
export VLLM_BASE_URL=http://<cloud-ip>:9001
export ACCELERATOR_LABEL="1x AMD Instinct MI300X (192 GB VRAM)"
# Restart the API — it will use vLLM instead of local_vlm
```

The bridge needs no changes. The same ROS2 bag plays, the same POST goes to the API,
but now Qwen-VL runs in full BF16 on MI300X at full speed.
