from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["watch", "elevated", "critical"]
EvidenceKind = Literal["image", "video", "report", "sensor", "audio"]
UncertaintyKind = Literal["missing_data", "model_disagreement", "stale_evidence", "simulation_sensitivity"]


class EvidenceItem(BaseModel):
    id: str
    sourceUuid: str
    source: str
    kind: EvidenceKind
    summary: str
    confidence: float = Field(ge=0, le=1)
    signal: str
    linkedZoneId: str | None = None
    assetUrl: str | None = None
    transcript: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class RiskZone(BaseModel):
    id: str
    label: str
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    radius: float = Field(gt=0, le=50)
    severity: Severity
    rationale: str


class ResponseAction(BaseModel):
    id: str
    title: str
    owner: str
    etaMinutes: int = Field(ge=0)
    impact: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    caveat: str
    sourceEntityId: str
    status: Literal["candidate", "approved"] = "candidate"


class UncertaintyIssue(BaseModel):
    id: str
    kind: UncertaintyKind
    title: str
    detail: str
    severity: Severity
    sourceEntityIds: list[str]


class GpuLane(BaseModel):
    label: str
    workload: str
    utilization: int = Field(ge=0, le=100)
    memoryGb: int = Field(ge=0)
    latencyMs: int = Field(ge=0)


class Scenario(BaseModel):
    incident: str
    category: str
    location: str
    clock: str
    thesis: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceItem]
    zones: list[RiskZone]
    actions: list[ResponseAction]
    uncertainties: list[UncertaintyIssue]
    gpu: list[GpuLane]
    brief: list[str]


class IngestRequest(BaseModel):
    location: str
    field_notes: str
    media_count: int = Field(default=0, ge=0, le=10)
    sensor_count: int = Field(default=0, ge=0, le=20)
    sensor_trace: list[dict] = Field(default_factory=list)


class TranscribeResponse(BaseModel):
    text: str
    confidence: float
    backend: str


class IngestResponse(BaseModel):
    ok: bool
    scenario: Scenario
    runtime_plan: list[str]
