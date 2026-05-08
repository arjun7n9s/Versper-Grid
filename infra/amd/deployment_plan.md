# AMD MI300X Deployment Plan

## Hardware Target

The provided AMD Developer Cloud profile is the canonical deployment target:

- 1x AMD MI300X GPU
- 192 GB VRAM
- 20 vCPU
- 240 GB RAM
- 720 GB boot NVMe SSD
- 5 TB scratch NVMe SSD

This single-GPU shape keeps deployment simple: one warm Qwen-VL server on GPU 0, deterministic fallback in the API, and CPU/RAM workers for graph and simulation tasks.

## Recommended Image

Start with the vLLM quick-start image:

- vLLM 0.17.1
- ROCm 7.2.0
- optimized for LLM inference and serving

Fallbacks:

- SGLang 0.5.9 for structured serving and multi-request scheduling
- PyTorch 2.6.0 ROCm image for custom simulation kernels
- ROCm Software image for maximum manual control

## Runtime Topology

```text
Nginx / Caddy
  |
  +-- Vesper Console static build
  |
  +-- Vesper API :8742
        |
        +-- Qwen-VL server :9001
        +-- Embedding worker pool
        +-- Simulation worker pool
        +-- Evidence graph / cache
```

## Runtime Allocation

| Resource | Role |
| --- | --- |
| GPU 0 | Qwen-VL image and five-keyframe reasoning through vLLM with TP=1 |
| CPU/RAM | embedding batches, entity normalization, in-memory graph scoring, and route/hazard simulation |
| API fallback | deterministic synthesis when the model endpoint is unavailable |

## Storage Plan

- Boot disk: app, model server configs, system packages
- Scratch disk: model weights, frame cache, embeddings, scenario cache, logs
- Keep generated caches disposable and reproducible
- Never store private demo credentials in repository

## Observability

Expose:

- model server health
- queue depth
- p50/p95 latency
- frame batch size
- GPU utilization
- VRAM allocation
- end-to-end multimodal latency
- cache hit rate
- candidate-plan confidence

## Demo Commands

```bash
python -m pip install -r apps/api/requirements.txt
npm install
npm run build
npm run api
```

For production, use `scripts/bootstrap_amd_cloud.sh` after cloning the repository to `/opt/vespergrid`.
