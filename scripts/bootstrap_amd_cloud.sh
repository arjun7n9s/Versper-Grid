#!/usr/bin/env bash
# VesperGrid one-shot bootstrap for AMD Developer Cloud (1x MI300X, 192 GB).
#
# Designed for the "vLLM 0.17.1 / ROCm 7.2.0" quick-start image so vLLM is
# already installed system-wide; we only add VesperGrid services on top.
# Single-GPU build: tensor-parallel-size 1, no NCCL/RCCL multi-GPU paths.
# Idempotent: safe to re-run.
#
# Usage:
#   sudo bash scripts/bootstrap_amd_cloud.sh
#
# Environment overrides:
#   APP_DIR                default: /opt/vespergrid (this checkout)
#   PYTHON_BIN             default: /opt/vespergrid-venv/bin/python
#   VLM_MODEL              default: Qwen/Qwen2.5-VL-7B-Instruct
#   VLM_PORT               default: 9001
#   API_PORT               default: 8742
#   CONSOLE_HOST_PORT      default: 80   (nginx reverse proxy front door)
#   PUBLIC_ORIGINS         default: http://localhost  (comma-separated CORS allowlist)
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/vespergrid}"
PYTHON_BIN="${PYTHON_BIN:-/opt/vespergrid-venv/bin/python}"
VLM_MODEL="${VLM_MODEL:-Qwen/Qwen2.5-VL-7B-Instruct}"
VLM_PORT="${VLM_PORT:-9001}"
API_PORT="${API_PORT:-8742}"
CONSOLE_HOST_PORT="${CONSOLE_HOST_PORT:-80}"
PUBLIC_ORIGINS="${PUBLIC_ORIGINS:-http://localhost}"

log() { printf "\n\033[1;36m[bootstrap]\033[0m %s\n" "$*"; }

if [[ ! -d "$APP_DIR" ]]; then
  echo "APP_DIR ($APP_DIR) does not exist. Clone the repo there first." >&2
  exit 1
fi

# ---- 1. System packages ----------------------------------------------------
log "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  git python3.12-venv python3-pip nodejs npm ffmpeg curl jq htop nginx

# ---- 2. Python venv for VesperGrid API -------------------------------------
log "Creating Python venv at /opt/vespergrid-venv"
if [[ ! -x "$PYTHON_BIN" ]]; then
  python3 -m venv /opt/vespergrid-venv
fi
"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
"$PYTHON_BIN" -m pip install -r "$APP_DIR/apps/api/requirements.txt"

# ---- 3. Console build ------------------------------------------------------
log "Building React console"
( cd "$APP_DIR" && npm install && npm run build )

# ---- 4. Generate demo assets if missing ------------------------------------
if [[ ! -f "$APP_DIR/apps/console/public/assets/vesper-field-map.png" ]]; then
  log "Generating procedural demo assets"
  "$PYTHON_BIN" -m pip install --quiet Pillow
  "$PYTHON_BIN" "$APP_DIR/scripts/generate_assets.py"
  ( cd "$APP_DIR" && npm run build )
fi

# ---- 5. Env file shared by both services -----------------------------------
log "Writing /etc/vespergrid/api.env"
mkdir -p /etc/vespergrid
cat >/etc/vespergrid/api.env <<EOF
PYTHONPATH=$APP_DIR/apps/api/src
VLLM_BASE_URL=http://127.0.0.1:$VLM_PORT
VLLM_MODEL=$VLM_MODEL
VLLM_API_KEY=vespergrid-local
VLLM_TIMEOUT_SECONDS=90
VLLM_MAX_FRAMES=5
VESPER_CORS_ORIGINS=$PUBLIC_ORIGINS
EOF
chmod 0644 /etc/vespergrid/api.env

# ---- 6. systemd: vLLM Qwen-VL on the single MI300X (TP=1) ------------------
log "Installing vespergrid-vllm.service (Qwen-VL on single MI300X)"
cat >/etc/systemd/system/vespergrid-vllm.service <<EOF
[Unit]
Description=VesperGrid vLLM (Qwen-VL on single MI300X, 192 GB VRAM)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=HIP_VISIBLE_DEVICES=0
Environment=PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/env python3 -m vllm.entrypoints.openai.api_server \\
  --model $VLM_MODEL \\
  --tensor-parallel-size 1 \\
  --port $VLM_PORT \\
  --max-model-len 8192 \\
  --gpu-memory-utilization 0.85 \\
  --trust-remote-code \\
  --limit-mm-per-prompt image=5
Restart=on-failure
RestartSec=15
TimeoutStartSec=600
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ---- 7. systemd: VesperGrid API --------------------------------------------
log "Installing vespergrid-api.service"
cat >/etc/systemd/system/vespergrid-api.service <<EOF
[Unit]
Description=VesperGrid API (FastAPI / Uvicorn)
After=network-online.target vespergrid-vllm.service
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/vespergrid/api.env
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON_BIN -m uvicorn vespergrid.main:app --host 0.0.0.0 --port $API_PORT
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# ---- 8. nginx reverse proxy ------------------------------------------------
log "Installing nginx site"
cat >/etc/nginx/sites-available/vespergrid <<EOF
server {
    listen $CONSOLE_HOST_PORT default_server;
    server_name _;

    # Static console build
    root $APP_DIR/apps/console/dist;
    index index.html;

    # API proxy (SSE-safe: long timeouts, no buffering)
    location /api/ {
        proxy_pass http://127.0.0.1:$API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # SSE / streaming
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        chunked_transfer_encoding on;
    }

    # SPA fallback
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
ln -sf /etc/nginx/sites-available/vespergrid /etc/nginx/sites-enabled/vespergrid
rm -f /etc/nginx/sites-enabled/default
nginx -t

# ---- 9. Boot services ------------------------------------------------------
log "Reloading and enabling services"
systemctl daemon-reload
systemctl enable --now vespergrid-vllm.service
systemctl enable --now vespergrid-api.service
systemctl restart nginx

# ---- 10. Warm-up & smoke test ---------------------------------------------
log "Waiting for vLLM to become reachable (up to 5 min)"
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$VLM_PORT/v1/models" >/dev/null 2>&1; then
    log "vLLM is up after ${i}x5s"
    break
  fi
  sleep 5
done

log "API health"
curl -fsS "http://127.0.0.1:$API_PORT/api/health" | jq . || true

log "Cold-start warm-up (single empty multimodal request)"
curl -fsS -X POST "http://127.0.0.1:$API_PORT/api/ingest" \
     -H 'content-type: application/json' \
     -d '{"location":"warm-up","field_notes":"bootstrap warm-up","media_count":0,"sensor_count":0}' \
     | tee /tmp/vespergrid-warmup.json
echo

log "Done. Console available at http://<host>:$CONSOLE_HOST_PORT"
log "  systemctl status vespergrid-vllm vespergrid-api nginx"
log "  journalctl -u vespergrid-vllm -f      (model load logs)"
log "  journalctl -u vespergrid-api  -f      (API logs)"
