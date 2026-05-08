# VesperGrid

> **Critical infrastructure operational twin for AMD MI300X.** VesperGrid turns fragmented industrial evidence into a source-linked decision-support model that explains what is happening, what may happen next, and which candidate plan is safest under uncertainty.

**Hackathon track:** Vision & Multimodal AI
**Optional prize alignment:** Qwen Challenge, Hugging Face Special Prize, Build-in-Public

## Product Thesis

Industrial operators often receive scattered signals during high-pressure incidents: drone frames, fixed-camera footage, sensor readings, radio notes, and partial field reports. The hard part is not getting one more chatbot answer. The hard part is seeing which evidence supports which decision, where the uncertainty lives, and what action is safest under time pressure.

VesperGrid is designed as an **evidence-to-simulation console** for that moment. The demo scenario, **Sector 4 Solvent Containment**, is fully synthetic and fictional.

## AMD Cloud Target

This repository is being built around the corrected AMD Developer Cloud machine:

| Resource | Target |
|----------|--------|
| GPU | 1x AMD Instinct MI300X |
| GPU memory | 192 GB VRAM |
| CPU | 20 vCPU |
| System memory | 240 GB RAM |
| Boot disk | 720 GB NVMe |
| Scratch disk | 5 TB NVMe |
| Preferred quick-start | vLLM 0.17.1 + ROCm 7.2.0 |

The architecture assumes one large-memory MI300X, not an eight-GPU cluster. That makes the strategy sharper: keep one multimodal model warm, cap evidence batches carefully, stream progress to the UI, and use deterministic fallback paths for demo reliability.

## Planned Architecture

```text
Gazebo / ROS2 evidence stream
  drone frame / CCTV still / gas trace / voice report
              |
              v
       multimodal ingest service
              |
      +-------+--------+
      |                |
 deterministic    Qwen-VL via vLLM
 fallback         on AMD MI300X
      |                |
      +-------+--------+
              |
              v
 source-linked operational twin
  evidence mesh / risk zones / candidate plan
  uncertainty ledger / runtime telemetry
              |
              v
 incident-command React operations console
```

## Repository Direction

The codebase is being pushed in deliberate, meaningful stages so the public history reads like a real product forming:

1. **Product foundation:** corrected identity, hardware target, README, license, and basic app scaffolding.
2. **Scenario source of truth:** Sector 4 schema, typed scenario data, synthetic evidence manifest.
3. **Async ingest pipeline:** FastAPI job lifecycle, progress events, deterministic fallback.
4. **MI300X inference path:** vLLM-compatible Qwen-VL client and runtime configuration.
5. **Console experience:** incident-command dashboard, source lineage, uncertainty ledger, voice channel, sensor trend, and response options.
6. **Synthetic asset system:** procedural maps, sensor strips, CCTV/drone frames, audit samples.
7. **Deployment package:** AMD cloud bootstrap, Hugging Face Space strategy, demo readiness notes.

## Demo Scenario

The first scenario is **Sector 4 Solvent Containment**, a fictional industrial safety incident in a synthetic port logistics corridor.

The source-of-truth scenario lives at `apps/console/src/data/sector4.json` and is shared across the stack:

- FastAPI validates it through Pydantic models in `apps/api/src/vespergrid/models.py`.
- The deterministic scenario loader in `apps/api/src/vespergrid/engine.py` returns fresh validated copies for API workflows.
- The console reads the same JSON through `apps/console/src/domain.ts` so UI state, backend state, and demo docs cannot drift apart.

The scenario encodes source-linked evidence, risk zones, candidate actions, uncertainty issues, MI300X runtime telemetry, and an incident state summary.

## API Surface

The FastAPI service now exposes a deterministic async ingest lifecycle:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Liveness, product metadata, accelerator target, runtime plan |
| `GET` | `/api/scenarios/sector-4-containment` | Returns the validated Sector 4 operational twin |
| `POST` | `/api/ingest` | Creates an ingest job and returns immediately with `{ job_id, status, backend }` |
| `POST` | `/api/ingest/upload` | Creates an ingest job from image/audio evidence and optional structured sensor trace |
| `POST` | `/api/audio/transcribe` | Transcribes an operator or worker voice clip with explicit fallback support |
| `GET` | `/api/ingest/{job_id}` | Returns the current job snapshot |
| `GET` | `/api/ingest/{job_id}/events` | Streams stage progress with Server-Sent Events |
| `POST` | `/api/ingest/{job_id}/await` | Bounded blocking helper for clients that cannot consume SSE |

The ingest path now accepts camera frames, voice clips, and gas/wind sensor traces. Visual evidence routes through Qwen-VL when a vLLM or local VLM backend is available, voice evidence routes through STT when configured with explicit transcript fallback, and numeric gas/wind traces are scored by deterministic signal analysis. The event stream exposes `queued -> sampling -> parsing/transcribing/analyzing -> normalizing -> synthesizing -> complete`.

## Why This Is Different

VesperGrid is not a generic assistant and not a reskinned dashboard. Its core interaction is **source lineage**: a judge can click any recommended action and see the exact evidence item that shaped it. The system is intentionally honest about uncertainty instead of hiding ambiguity behind confident prose.

## License & Data

The planned license is **Apache-2.0**, which is friendly to open-source judging, demos, research reuse, and future startup commercialization.

All demo assets and scenario data are synthetic. No real facility footage, maps, CCTV, or private operational data should be committed.

## Project Status

The public repository is being developed through small, reviewable milestones. Internal progress notes and competition working logs are intentionally kept out of Git so the repo stays focused on source code, reproducible assets, deployment notes, and judge-facing documentation.
