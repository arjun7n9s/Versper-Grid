"""Async ingest job manager.

Flow:
1. `POST /api/ingest/upload`  -> accepts multipart image files + manifest JSON,
                                 creates job, returns {job_id} immediately
2. `POST /api/ingest`         -> legacy JSON-only path (no images), deterministic
3. background task            -> runs real VLM pipeline, emits SSE events
4. `GET  /api/ingest/{id}/events` -> SSE stream consumed by the React console

VLM routing:
- VLLM_BASE_URL set  -> remote vLLM OpenAI-compatible endpoint (production/MI300X)
- VLLM_BASE_URL unset, CUDA available -> local_vlm.py transformers (RTX 5060)
- No GPU at all      -> deterministic synthesizer (offline demo / CI)
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import AsyncIterator, Literal

import logging
from pathlib import Path

from .engine import synthesize_from_ingest, synthesize_from_vlm_output
from .models import IngestRequest, Scenario
from .vlm_client import VLMClientError, is_enabled as vllm_enabled

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "complete", "failed"]
EventStage = Literal[
    "queued",
    "sampling",
    "parsing",
    "normalizing",
    "synthesizing",
    "complete",
    "error",
]

# Sentinel pushed onto a job's queue to signal end-of-stream to SSE consumers.
_END_OF_STREAM = object()


@dataclass
class JobEvent:
    seq: int
    ts: float
    stage: EventStage
    message: str
    progress: float  # 0..1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IngestJob:
    id: str
    status: JobStatus
    request: IngestRequest
    events: list[JobEvent] = field(default_factory=list)
    result: Scenario | None = None
    error: str | None = None
    image_paths: list[Path] = field(default_factory=list)
    backend: Literal["deterministic", "local_vlm", "vllm"] = "deterministic"
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    def snapshot(self) -> dict:
        return {
            "job_id": self.id,
            "status": self.status,
            "backend": self.backend,
            "events": [e.to_dict() for e in self.events],
            "result": self.result.model_dump() if self.result else None,
            "error": self.error,
        }


class JobRegistry:
    """In-memory job registry. Adequate for hackathon scope; the demo is a
    single-tenant, single-incident scenario. Production would back this with
    Redis or DuckDB and add TTL-based eviction."""

    def __init__(self, max_jobs: int = 256) -> None:
        self._jobs: dict[str, IngestJob] = {}
        self._max_jobs = max_jobs
        self._lock = asyncio.Lock()

    async def create(self, request: IngestRequest) -> IngestJob:
        async with self._lock:
            if len(self._jobs) >= self._max_jobs:
                # FIFO eviction; the oldest finished job goes first.
                for jid, j in list(self._jobs.items()):
                    if j.status in ("complete", "failed"):
                        self._jobs.pop(jid, None)
                        break
            job = IngestJob(
                id=uuid.uuid4().hex[:12],
                status="queued",
                request=request,
                backend="deterministic",
            )
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> IngestJob | None:
        return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[IngestJob]:
        jobs = list(self._jobs.values())
        return jobs[-limit:]

    async def emit(
        self,
        job: IngestJob,
        stage: EventStage,
        message: str,
        progress: float,
    ) -> None:
        ev = JobEvent(
            seq=len(job.events),
            ts=time.time(),
            stage=stage,
            message=message,
            progress=max(0.0, min(1.0, progress)),
        )
        job.events.append(ev)
        await job._queue.put(ev)

    async def close(self, job: IngestJob) -> None:
        await job._queue.put(_END_OF_STREAM)

    async def stream(self, job: IngestJob) -> AsyncIterator[JobEvent]:
        # Replay history first so latecomers see the full timeline.
        for ev in list(job.events):
            yield ev
        if job.status in ("complete", "failed"):
            return
        while True:
            item = await job._queue.get()
            if item is _END_OF_STREAM:
                return
            assert isinstance(item, JobEvent)
            yield item
            if item.stage in ("complete", "error"):
                return


registry = JobRegistry()


async def _run_pipeline(job: IngestJob) -> None:
    """Execute the multimodal pipeline. Stages are emitted as SSE events.

    Routing:
    - image_paths present + VLLM_BASE_URL set  -> remote vLLM (MI300X)
    - image_paths present + CUDA available     -> local transformers (RTX 5060)
    - no images / no GPU                       -> deterministic synthesizer
    """
    job.status = "running"
    try:
        await registry.emit(job, "queued", "Job accepted by orchestrator.", 0.05)
        await asyncio.sleep(0)

        n_images = len(job.image_paths)
        sensor_count = job.request.sensor_count
        await registry.emit(
            job,
            "sampling",
            f"Sampling {n_images} image frame(s) and {sensor_count} sensor trace(s).",
            0.15,
        )

        if job.image_paths:
            scenario = await _run_vlm_pipeline(job)
        else:
            await registry.emit(
                job, "parsing",
                "No images attached — running deterministic synthesizer.",
                0.45,
            )
            await registry.emit(
                job, "normalizing",
                "Normalizing observations into Entity / Location / Hazard / Constraint records.",
                0.75,
            )
            await registry.emit(
                job, "synthesizing",
                "Compiling source-linked candidate plan and uncertainty ledger.",
                0.90,
            )
            scenario = synthesize_from_ingest(job.request)

        job.result = scenario
        await registry.emit(
            job, "complete",
            f"Scenario ready — {len(scenario.evidence)} evidence item(s), "
            f"backend={job.backend}.",
            1.0,
        )
        job.status = "complete"
    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job.id)
        job.status = "failed"
        job.error = str(exc)
        await registry.emit(job, "error", f"Pipeline failed: {exc}", 1.0)
    finally:
        await registry.close(job)


async def _run_vlm_pipeline(job: IngestJob) -> Scenario:
    """Parse each image through Qwen-VL, then synthesize a real Scenario."""
    from .vlm_client import parse_evidence as parse_vllm
    from .local_vlm import parse_evidence_local

    use_vllm = vllm_enabled()
    job.backend = "vllm" if use_vllm else "local_vlm"

    parse_fn = parse_vllm if use_vllm else parse_evidence_local
    backend_label = "vLLM/MI300X" if use_vllm else "local Qwen2.5-VL/RTX"

    await registry.emit(
        job, "parsing",
        f"Sending {len(job.image_paths)} frame(s) to {backend_label} for multimodal parsing.",
        0.30,
    )

    bundles = []
    uuids = []
    for idx, img_path in enumerate(job.image_paths):
        source_uuid = img_path.stem.upper().replace("-", "_")[:24]
        uuids.append(source_uuid)
        try:
            img_bytes = img_path.read_bytes()
            bundle = await parse_fn(
                source_uuid=source_uuid,
                field_notes=job.request.field_notes,
                image_payloads=[img_bytes],
            )
            bundles.append(bundle)
            logger.info("VLM parsed %s: %d obs, %d unc",
                        source_uuid, len(bundle.observations), len(bundle.uncertainties))
        except VLMClientError as exc:
            logger.warning("VLM failed for %s: %s — skipping", source_uuid, exc)
        await registry.emit(
            job, "parsing",
            f"Parsed frame {idx + 1}/{len(job.image_paths)}: {source_uuid}",
            0.30 + 0.35 * (idx + 1) / len(job.image_paths),
        )

    await registry.emit(
        job, "normalizing",
        f"Normalizing {sum(len(b.observations) for b in bundles)} VLM observations.",
        0.72,
    )
    await registry.emit(
        job, "synthesizing",
        "Compiling source-linked candidate plan and uncertainty ledger.",
        0.88,
    )

    if not bundles:
        logger.warning("All VLM calls failed — falling back to deterministic")
        job.backend = "deterministic"
        return synthesize_from_ingest(job.request)

    return synthesize_from_vlm_output(
        bundles=bundles,
        location=job.request.location,
        field_notes=job.request.field_notes,
        image_uuids=uuids,
    )


def schedule(job: IngestJob) -> asyncio.Task:
    """Detach the pipeline so the HTTP handler returns immediately."""
    return asyncio.create_task(_run_pipeline(job))
