"""VesperGrid HTTP surface.

Endpoints:
- GET  /api/health                              - liveness + runtime metadata
- GET  /api/scenarios/sector-4-containment      - deterministic scenario
- POST /api/ingest/upload                       - multipart image upload + manifest (real pipeline)
- POST /api/ingest                              - JSON-only legacy path (deterministic)
- GET  /api/ingest/{job_id}                     - snapshot of job state
- GET  /api/ingest/{job_id}/events              - SSE event stream
- POST /api/ingest/{job_id}/await               - blocking convenience
- GET  /api/evidence/{uuid}                     - serve uploaded image thumbnail
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from .engine import runtime_plan, sector_4_containment
from .ingest import IngestJob, registry, schedule
from .models import IngestRequest, Scenario, TranscribeResponse
from .stt import transcribe_audio
from .vlm_client import is_enabled as vllm_enabled

logger = logging.getLogger(__name__)

_EVIDENCE_DIR = Path(tempfile.gettempdir()) / "vespergrid_evidence"
_EVIDENCE_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="VesperGrid API",
    description="Multimodal evidence-to-simulation orchestration API for AMD MI300X deployments.",
    version="0.1.0",
)


def _allowed_origins() -> list[str]:
    raw = os.environ.get("VESPER_CORS_ORIGINS", "")
    if not raw:
        # Sensible local-dev default. Production deployments must set this
        # explicitly to the HF Space + cloud console origins.
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    if raw.strip() == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, object]:
    cuda_ok = False
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
    except Exception:
        pass
    backend = "vllm" if vllm_enabled() else ("local_vlm" if cuda_ok else "deterministic")
    return {
        "ok": True,
        "product": "VesperGrid",
        "track": "Vision & Multimodal AI",
        "positioning": "Critical Infrastructure Operational Twin",
        "accelerator_target": os.environ.get(
            "ACCELERATOR_LABEL", "1x AMD Instinct MI300X (192 GB VRAM)"
        ),
        "vlm_backend": backend,
        "runtime_plan": runtime_plan(),
    }


@app.get("/api/scenarios/sector-4-containment", response_model=Scenario)
async def scenario() -> Scenario:
    return sector_4_containment()


@app.post("/api/ingest/upload")
async def ingest_upload(
    images: list[UploadFile] = File(default=[]),
    audio: list[UploadFile] = File(default=[]),
    location: str = Form(default="Unknown location"),
    field_notes: str = Form(default=""),
    sensor_count: int = Form(default=0),
    sensor_trace: str = Form(default="[]"),
    voice_manifest: str = Form(default="[]"),
) -> dict:
    """Real ingest path: accepts camera frames, voice clips, and sensor traces."""
    sensor_samples = _parse_json_list(sensor_trace, "sensor_trace")
    voice_reports = _parse_json_list(voice_manifest, "voice_manifest")
    req = IngestRequest(
        location=location,
        field_notes=field_notes,
        media_count=len(images),
        sensor_count=min(20, max(sensor_count, len(sensor_samples))),
        sensor_trace=sensor_samples[:20],
    )
    job = await registry.create(req)

    job_dir = _EVIDENCE_DIR / job.id
    job_dir.mkdir(exist_ok=True)
    saved_paths = []
    for upload in images:
        safe_name = Path(upload.filename or f"frame_{len(saved_paths)}.jpg").name
        dest = job_dir / safe_name
        with dest.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
        saved_paths.append(dest)
        logger.info("Saved uploaded image: %s", dest)

    job.image_paths = saved_paths
    audio_paths = []
    for upload in audio:
        safe_name = Path(upload.filename or f"voice_{len(audio_paths)}.webm").name
        dest = job_dir / safe_name
        with dest.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
        audio_paths.append(dest)
        logger.info("Saved uploaded audio: %s", dest)

    job.audio_paths = audio_paths
    job.voice_reports = voice_reports
    job.sensor_trace = sensor_samples
    schedule(job)
    return {"job_id": job.id, "status": job.status, "backend": job.backend,
            "image_count": len(saved_paths), "audio_count": len(audio_paths),
            "sensor_samples": len(sensor_samples)}


def _parse_json_list(raw: str, field_name: str) -> list[dict]:
    if not raw or raw.strip() in ("", "[]"):
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be valid JSON") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=422, detail=f"{field_name} must be a JSON list")
    if not all(isinstance(item, dict) for item in data):
        raise HTTPException(status_code=422, detail=f"{field_name} entries must be objects")
    return data


@app.post("/api/ingest")
async def ingest(request: IngestRequest) -> dict:
    job = await registry.create(request)
    schedule(job)
    return {
        "job_id": job.id,
        "status": job.status,
        "backend": job.backend,
    }


@app.post("/api/audio/transcribe", response_model=TranscribeResponse)
async def audio_transcribe(
    audio: UploadFile = File(...),
    fallback_text: str = Form(default=""),
) -> TranscribeResponse:
    job_dir = _EVIDENCE_DIR / "transcribe"
    job_dir.mkdir(exist_ok=True)
    safe_name = Path(audio.filename or "operator_audio.webm").name
    dest = job_dir / f"{asyncio.get_event_loop().time():.6f}-{safe_name}"
    with dest.open("wb") as f:
        shutil.copyfileobj(audio.file, f)
    result = transcribe_audio(dest, fallback_text=fallback_text)
    return TranscribeResponse(text=result.text, confidence=result.confidence, backend=result.backend)


@app.get("/api/evidence/{uuid}/{filename}")
async def serve_evidence(uuid: str, filename: str):
    """Serve an uploaded Gazebo frame by source UUID + filename."""
    target = _EVIDENCE_DIR / uuid / filename
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="evidence file not found")
    media_type = (
        "audio/webm" if target.suffix.lower() in (".webm", ".ogg")
        else "audio/wav" if target.suffix.lower() == ".wav"
        else "audio/aac" if target.suffix.lower() == ".aac"
        else "image/jpeg"
    )
    return FileResponse(str(target), media_type=media_type)


@app.get("/api/feeds/latest/{source}")
async def latest_feed_frame(source: str):
    """Return the most recently uploaded frame whose filename starts with `source`.

    `source` matches camera prefixes used by frame_sampler:
      cctv_south  -> cctv_south_*.jpg
      drone_d1    -> drone_d1_*.jpg
      cctv_gate   -> cctv_gate_*.jpg

    Scans all job directories newest-first and returns the first match.
    Returns 404 if no frame has been uploaded yet.
    """
    best: Path | None = None
    best_mtime: float = 0.0

    if _EVIDENCE_DIR.exists():
        for job_dir in sorted(
            _EVIDENCE_DIR.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            if not job_dir.is_dir():
                continue
            for f in job_dir.iterdir():
                if f.is_file() and f.name.startswith(source) and f.suffix in (".jpg", ".jpeg", ".png"):
                    mt = f.stat().st_mtime
                    if mt > best_mtime:
                        best_mtime = mt
                        best = f
            if best is not None:
                break   # newest job dir already had a match — stop

    if best is None:
        raise HTTPException(status_code=404, detail=f"no frame for source '{source}'")

    return FileResponse(
        str(best),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/api/feeds")
async def list_feeds():
    """Return available feed sources and their latest-frame URLs."""
    sources = ["cctv_south", "drone_d1", "cctv_gate"]
    result = []
    for src in sources:
        found = False
        if _EVIDENCE_DIR.exists():
            for job_dir in sorted(
                _EVIDENCE_DIR.iterdir(),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            ):
                if not job_dir.is_dir():
                    continue
                for f in job_dir.iterdir():
                    if f.is_file() and f.name.startswith(src):
                        found = True
                        break
                if found:
                    break
        result.append({"source": src, "available": found, "url": f"/api/feeds/latest/{src}"})
    return result


@app.get("/api/jobs")
async def list_jobs(limit: int = 20) -> list[dict]:
    """Return recent job summaries — used by the dashboard ticker to discover
    jobs submitted by frame_sampler (and any other producers)."""
    jobs = registry.list_recent(limit=min(limit, 50))
    return [
        {
            "job_id": j.id,
            "status": j.status,
            "backend": j.backend,
            "stage": j.events[-1].stage if j.events else "queued",
            "progress": j.events[-1].progress if j.events else 0.0,
            "message": j.events[-1].message if j.events else "",
            "ts": j.events[-1].ts if j.events else 0.0,
        }
        for j in reversed(jobs)
    ]


def _require_job(job_id: str) -> IngestJob:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/api/ingest/{job_id}")
async def ingest_status(job_id: str) -> dict:
    return _require_job(job_id).snapshot()


@app.get("/api/ingest/{job_id}/events")
async def ingest_events(job_id: str, request: Request):
    job = _require_job(job_id)

    async def event_generator():
        async for ev in registry.stream(job):
            if await request.is_disconnected():
                break
            yield {
                "event": ev.stage,
                "id": str(ev.seq),
                "data": json.dumps(ev.to_dict()),
            }
        # Final frame so the client knows the stream is done and can read
        # the result snapshot in one hop.
        yield {
            "event": "snapshot",
            "data": json.dumps(job.snapshot()),
        }

    return EventSourceResponse(event_generator())


@app.post("/api/ingest/{job_id}/await")
async def ingest_await(job_id: str, timeout_seconds: float = 30.0) -> dict:
    """Blocking convenience for clients that cannot stream. Bounded so a
    stuck pipeline cannot deadlock a caller."""
    job = _require_job(job_id)
    deadline = asyncio.get_event_loop().time() + max(1.0, min(timeout_seconds, 120.0))
    while job.status not in ("complete", "failed"):
        if asyncio.get_event_loop().time() >= deadline:
            raise HTTPException(status_code=504, detail="job did not complete in time")
        await asyncio.sleep(0.1)
    return job.snapshot()
