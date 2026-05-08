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
from .models import IngestRequest, Scenario
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
    location: str = Form(default="Unknown location"),
    field_notes: str = Form(default=""),
    sensor_count: int = Form(default=0),
) -> dict:
    """Real ingest path: accepts multipart image files from the ROS2 bridge."""
    req = IngestRequest(
        location=location,
        field_notes=field_notes,
        media_count=len(images),
        sensor_count=sensor_count,
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
    schedule(job)
    return {"job_id": job.id, "status": job.status, "backend": job.backend,
            "image_count": len(saved_paths)}


@app.post("/api/ingest")
async def ingest(request: IngestRequest) -> dict:
    job = await registry.create(request)
    schedule(job)
    return {
        "job_id": job.id,
        "status": job.status,
        "backend": job.backend,
    }


@app.get("/api/evidence/{uuid}/{filename}")
async def serve_evidence(uuid: str, filename: str):
    """Serve an uploaded Gazebo frame by source UUID + filename."""
    target = _EVIDENCE_DIR / uuid / filename
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="evidence file not found")
    return FileResponse(str(target), media_type="image/jpeg")


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
