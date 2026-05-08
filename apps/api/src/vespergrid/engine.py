"""Scenario engine.

The deterministic Sector 4 scenario lives in a single JSON file shared with
the React console (`apps/console/src/data/sector4.json`). This module loads
that JSON, validates it through Pydantic, and applies bounded mutations for
the live-ingest path. When `VLLM_BASE_URL` is set the ingest path delegates
to the Qwen-VL client; otherwise it falls back to deterministic synthesis so
the demo remains reproducible even with no GPU backend.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import (
    EvidenceItem,
    IngestRequest,
    ResponseAction,
    RiskZone,
    Scenario,
    UncertaintyIssue,
)

# engine.py -> vespergrid -> src -> api -> apps -> console/src/data/sector4.json
_SCENARIO_PATH = (
    Path(__file__).resolve().parents[3]
    / "console"
    / "src"
    / "data"
    / "sector4.json"
)


@lru_cache(maxsize=1)
def _load_sector4() -> dict:
    if not _SCENARIO_PATH.exists():
        raise FileNotFoundError(
            f"Sector 4 scenario JSON not found at {_SCENARIO_PATH}. "
            "Frontend and API share this file; do not delete it."
        )
    return json.loads(_SCENARIO_PATH.read_text(encoding="utf-8"))


def sector_4_containment() -> Scenario:
    """Return a fresh Pydantic-validated copy of the deterministic scenario."""
    return Scenario.model_validate(_load_sector4())


def synthesize_from_ingest(request: IngestRequest) -> Scenario:
    """Deterministic synthesis used when no live VLM backend is configured.

    Bounded transformation: nudges confidence based on evidence pressure and
    appends a source-linked operator note + uncertainty if field notes were
    provided. Real model integration lives in `vlm_client.py` and is invoked
    by the async ingest path in `main.py` when `VLLM_BASE_URL` is set.
    """
    base = sector_4_containment()
    evidence_pressure = min(
        0.08,
        (request.media_count * 0.009) + (request.sensor_count * 0.002),
    )
    base.location = request.location
    base.confidence = min(0.94, base.confidence + evidence_pressure)

    field_note = request.field_notes.strip()
    if field_note:
        base.evidence.append(
            EvidenceItem(
                id="ev-live-notes",
                sourceUuid="SRC-LIVE-9001",
                source="Live operator note",
                kind="report",
                summary=field_note[:220],
                confidence=0.71,
                signal="human context",
                linkedZoneId="z3",
            )
        )
        base.uncertainties.append(
            UncertaintyIssue(
                id="u-live",
                kind="missing_data",
                title="Live note needs verification",
                detail=(
                    "The newest operator note was preserved, but VesperGrid "
                    "has not yet received confirming imagery."
                ),
                severity="watch",
                sourceEntityIds=["SRC-LIVE-9001"],
            )
        )
        base.brief.append(
            "Live operator note was added as a source-linked graph observation."
        )
    return base


def synthesize_from_vlm_output(
    bundles: list,
    location: str,
    field_notes: str,
    image_uuids: list[str],
) -> Scenario:
    """Build a real Scenario from one or more VLMObservationsBundle objects.

    Each bundle corresponds to one source (drone cam frame, CCTV clip, etc.).
    Observations are normalised into EvidenceItem + RiskZone + ResponseAction.
    Contradictions between bundles become UncertaintyIssue records.
    """
    import time

    evidence: list[EvidenceItem] = []
    zones: list[RiskZone] = []
    actions: list[ResponseAction] = []
    uncertainties: list[UncertaintyIssue] = []
    brief_lines: list[str] = []

    hazard_sources: list[str] = []
    clear_sources: list[str] = []
    all_confidences: list[float] = []

    _ZONE_COORDS = [
        (30.0, 40.0), (55.0, 60.0), (20.0, 70.0), (70.0, 30.0),
    ]
    _SEVERITY_MAP = {"Entity": "watch", "Location": "watch", "Hazard": "elevated", "Constraint": "critical"}

    for idx, bundle in enumerate(bundles):
        uuid = bundle.source_uuid
        obs_list = bundle.observations
        unc_list = bundle.uncertainties

        for obs_idx, obs in enumerate(obs_list):
            ev_id = f"ev-{uuid[:8]}-{obs_idx}"
            severity = _SEVERITY_MAP.get(obs.type, "watch")

            evidence.append(EvidenceItem(
                id=ev_id,
                sourceUuid=uuid,
                source=obs.entity,
                kind="image" if "cam" in uuid.lower() or "drone" in uuid.lower() else
                      "sensor" if "sensor" in uuid.lower() else "report",
                summary=obs.observation,
                confidence=obs.confidence,
                signal=obs.type.lower(),
                linkedZoneId=f"z{(idx % 4) + 1}",
            ))
            all_confidences.append(obs.confidence)

            if obs.type == "Hazard":
                hazard_sources.append(uuid)
                cx, cy = _ZONE_COORDS[idx % len(_ZONE_COORDS)]
                zones.append(RiskZone(
                    id=f"z{len(zones) + 1}",
                    label=obs.entity,
                    x=cx,
                    y=cy,
                    radius=12.0,
                    severity=severity,
                    rationale=obs.observation,
                ))
                actions.append(ResponseAction(
                    id=f"act-{len(actions) + 1}",
                    title=f"Respond to {obs.entity}",
                    owner="Safety team",
                    etaMinutes=max(3, int((1.0 - obs.confidence) * 15)),
                    impact=int(obs.confidence * 100),
                    confidence=obs.confidence,
                    caveat=obs.observation[:120],
                    sourceEntityId=uuid,
                    status="candidate",
                ))

        for unc in unc_list:
            uncertainties.append(UncertaintyIssue(
                id=f"u-{uuid[:8]}-{len(uncertainties)}",
                kind=unc.kind,
                title=f"Uncertainty in {uuid[:16]}",
                detail=unc.detail,
                severity="watch",
                sourceEntityIds=[uuid],
            ))
            clear_sources.append(uuid)

    if hazard_sources and clear_sources:
        contradicting = list(set(hazard_sources) & set(clear_sources))
        if contradicting:
            uncertainties.append(UncertaintyIssue(
                id="u-cross-sensor",
                kind="model_disagreement",
                title="Cross-sensor hazard contradiction",
                detail=(
                    "At least one source flags a hazard while another source "
                    "is uncertain or contradicts it. Confirm via additional sensor."
                ),
                severity="elevated",
                sourceEntityIds=contradicting,
            ))

    if field_notes.strip():
        evidence.append(EvidenceItem(
            id="ev-live-notes",
            sourceUuid="SRC-LIVE-9001",
            source="Live operator note",
            kind="report",
            summary=field_notes.strip()[:220],
            confidence=0.71,
            signal="human context",
            linkedZoneId="z1",
        ))
        brief_lines.append("Operator field note recorded and linked to evidence graph.")

    if not evidence:
        return sector_4_containment()

    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.5
    hazard_count = len([e for e in evidence if e.signal == "hazard"])
    brief_lines.insert(0, (
        f"Qwen2.5-VL analysed {len(bundles)} source(s) and identified "
        f"{len(evidence)} observations including {hazard_count} hazard signal(s)."
    ))
    if uncertainties:
        brief_lines.append(
            f"{len(uncertainties)} uncertainty issue(s) require operator verification."
        )

    from .models import GpuLane
    import subprocess, shutil
    gpu_lanes = _get_gpu_lanes()

    return Scenario(
        incident="VLM-Analysed Incident",
        category="Multimodal AI Assessment",
        location=location,
        clock=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        thesis=brief_lines[0] if brief_lines else "VLM analysis complete.",
        confidence=round(avg_confidence, 3),
        evidence=evidence,
        zones=zones if zones else [RiskZone(
            id="z1", label="Unconfirmed zone", x=50.0, y=50.0,
            radius=10.0, severity="watch",
            rationale="No explicit hazard zone identified by VLM.",
        )],
        actions=actions if actions else [],
        uncertainties=uncertainties,
        gpu=gpu_lanes,
        brief=brief_lines,
    )


def _get_gpu_lanes() -> list:
    """Query real GPU utilization from nvidia-smi if available, else static."""
    from .models import GpuLane
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            timeout=3, text=True,
        ).strip().splitlines()
        if out:
            parts = out[0].split(",")
            util = int(parts[0].strip())
            mem_used = int(parts[1].strip()) // 1024
            mem_total = int(parts[2].strip()) // 1024
            return [
                GpuLane(label="Qwen-VL parser", workload="multimodal inference",
                        utilization=util, memoryGb=mem_used, latencyMs=0),
                GpuLane(label="KV cache", workload="attention cache",
                        utilization=max(0, util - 10), memoryGb=max(0, mem_used - 1),
                        latencyMs=0),
                GpuLane(label="Image decode", workload="pixel preprocessing",
                        utilization=max(0, util - 20), memoryGb=1, latencyMs=0),
                GpuLane(label="Headroom", workload="available",
                        utilization=0, memoryGb=max(0, mem_total - mem_used), latencyMs=0),
            ]
    except Exception:
        pass
    return [
        GpuLane(label="Qwen-VL parser", workload="multimodal inference",
                utilization=72, memoryGb=6, latencyMs=0),
        GpuLane(label="KV cache", workload="attention cache",
                utilization=60, memoryGb=2, latencyMs=0),
        GpuLane(label="Image decode", workload="pixel preprocessing",
                utilization=45, memoryGb=1, latencyMs=0),
        GpuLane(label="Headroom", workload="available",
                utilization=0, memoryGb=2, latencyMs=0),
    ]


def runtime_plan() -> list[str]:
    return [
        "Serve Qwen-VL through vLLM ROCm on a single MI300X (TP=1, 192 GB VRAM).",
        "Sample up to five keyframes per clip and submit them as a single multi-image request.",
        "Normalize model outputs into Entity, Location, Hazard, and Constraint records with strict Pydantic validation.",
        "Keep graph/vector state in 240 GB system RAM for the demo; flush asynchronously to the 5 TB scratch NVMe.",
        "Run the simulation layer as CPU/vectorized MVP while GPU-resident multimodal inference demonstrates MI300X value.",
    ]
