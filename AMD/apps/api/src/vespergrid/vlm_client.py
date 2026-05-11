"""Qwen-VL client (vLLM OpenAI-compatible endpoint).

Design contract:
- If `VLLM_BASE_URL` is unset, `is_enabled()` returns False and callers must
  fall back to `engine.synthesize_from_ingest`. This guarantees the demo runs
  with no GPU backend.
- When enabled, we POST a multi-image chat completion to vLLM serving
  Qwen-VL (default model `Qwen/Qwen2.5-VL-7B-Instruct`). Up to 5 sampled
  keyframes are passed in a single request as the expert review recommended.
- The model is instructed to return strict JSON conforming to
  `VLMObservationsBundle`. Output is validated by Pydantic; on parse failure
  we raise `VLMClientError` and the caller falls back to deterministic
  synthesis (never hallucinated fields silently injected into UI state).

Environment variables:
- `VLLM_BASE_URL`         e.g. http://127.0.0.1:9001 (no trailing slash)
- `VLLM_MODEL`            default: Qwen/Qwen2.5-VL-7B-Instruct
- `VLLM_API_KEY`          optional; vLLM allows any non-empty token
- `VLLM_TIMEOUT_SECONDS`  default: 90
- `VLLM_MAX_FRAMES`       default: 5 (hard ceiling, expert recommendation)
"""
from __future__ import annotations

import base64
import json
import os
from typing import Iterable, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError


class VLMClientError(RuntimeError):
    """Raised when the VLM call fails or returns unparseable output."""


class VLMObservation(BaseModel):
    entity: str
    type: Literal["Entity", "Location", "Hazard", "Constraint"]
    observation: str
    confidence: float = Field(ge=0, le=1)
    location_hint: str | None = None


class VLMUncertainty(BaseModel):
    kind: Literal[
        "missing_data",
        "model_disagreement",
        "stale_evidence",
        "simulation_sensitivity",
    ]
    detail: str


class VLMObservationsBundle(BaseModel):
    """Strict schema the VLM is asked to follow. Drop everything outside this."""

    source_uuid: str
    observations: list[VLMObservation] = Field(default_factory=list, max_length=12)
    uncertainties: list[VLMUncertainty] = Field(default_factory=list, max_length=8)


_SYSTEM_PROMPT = (
    "You are VesperGrid's multimodal evidence parser for an industrial safety "
    "operational twin at a fictional LNG terminal. You receive up to 5 sampled "
    "keyframes, which may come from different camera angles (drone forward-cam, "
    "drone back-cam, CCTV south, CCTV gate). Treat the entire frame set as a "
    "cross-camera bundle for the same incident and correlate observations "
    "across angles before concluding.\n\n"
    "Rules:\n"
    "1. Return ONLY a single JSON object conforming exactly to VLMObservationsBundle. "
    "No markdown fences, no commentary outside JSON.\n"
    "2. For EACH confirmed Hazard observation, generate at least 2 distinct "
    "response-action observations of type Constraint: one immediate containment "
    "action and one monitoring/verification action. Label them clearly.\n"
    "3. If the same feature (smoke plume, liquid pool, heat signature) is visible "
    "from more than one camera angle, set confidence higher (up to 0.95). If "
    "cameras disagree on the extent of a hazard, emit a model_disagreement "
    "uncertainty citing both views.\n"
    "4. If a camera angle shows no relevant data for the active incident, emit a "
    "stale_evidence uncertainty for that angle — do not invent observations.\n"
    "5. Use confidence in [0,1]. Allowed observation types: Entity, Location, "
    "Hazard, Constraint. Allowed uncertainty kinds: missing_data, "
    "model_disagreement, stale_evidence, simulation_sensitivity.\n"
    "6. The source_uuid is the canonical identifier for this bundle — cite it on "
    "every observation."
)


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def is_enabled() -> bool:
    """True iff a vLLM endpoint is configured. Used by the ingest path to
    decide between live inference and deterministic synthesis."""
    return bool(_env("VLLM_BASE_URL"))


def _data_url_for(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def _build_messages(
    source_uuid: str,
    field_notes: str,
    image_data_urls: list[str],
    historical_context: str = "",
) -> list[dict]:
    user_content: list[dict] = []
    for url in image_data_urls:
        user_content.append({"type": "image_url", "image_url": {"url": url}})
    context_block = f"\n\n{historical_context}" if historical_context else ""
    user_content.append(
        {
            "type": "text",
            "text": (
                f"source_uuid: {source_uuid}\n"
                f"operator_field_notes: {field_notes or '(none)'}"
                f"{context_block}\n"
                "Return the JSON now."
            ),
        }
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _strip_json(text: str) -> str:
    """Best-effort strip of ```json fences and surrounding chatter."""
    s = text.strip()
    if s.startswith("```"):
        # remove leading fence (```json or ```)
        s = s.split("\n", 1)[-1]
    if s.endswith("```"):
        s = s[: s.rfind("```")]
    # find outermost JSON object
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s


async def parse_evidence(
    *,
    source_uuid: str,
    field_notes: str,
    image_payloads: Iterable[bytes],
    image_mime: str = "image/jpeg",
) -> VLMObservationsBundle:
    """Send a multi-image multimodal request to Qwen-VL via vLLM.

    Caller is responsible for sampling/downscaling frames before passing
    them in. We hard-cap at `VLLM_MAX_FRAMES` to avoid OOM (expert review
    failure mode #1 on ROCm).
    """
    if not is_enabled():
        raise VLMClientError("VLLM_BASE_URL is not configured")

    base_url = _env("VLLM_BASE_URL", "").rstrip("/").removesuffix("/v1")
    model = _env("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
    api_key = _env("VLLM_API_KEY", "vespergrid-local")
    timeout = float(_env("VLLM_TIMEOUT_SECONDS", "90"))
    max_frames = int(_env("VLLM_MAX_FRAMES", "5"))

    images = list(image_payloads)[:max_frames]
    image_urls = [_data_url_for(img, mime=image_mime) for img in images]

    # RAG: retrieve similar historical incidents and inject as context
    historical_context = ""
    try:
        from .memory import retrieve_similar, format_precedents
        query = f"{field_notes or ''} LNG terminal gas leak sensor trace camera evidence"
        hits = retrieve_similar(query, n=2)
        historical_context = format_precedents(hits)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("RAG retrieval skipped: %s", exc)

    payload = {
        "model": model,
        "messages": _build_messages(source_uuid, field_notes, image_urls, historical_context),
        "temperature": 0.1,
        "max_tokens": 768,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise VLMClientError(f"vLLM request failed: {exc}") from exc

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VLMClientError(f"unexpected vLLM response shape: {data!r}") from exc

    cleaned = _strip_json(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise VLMClientError(
            f"VLM did not return valid JSON: {text[:400]!r}"
        ) from exc

    # Force the source_uuid to the one we issued (defends against drift)
    parsed["source_uuid"] = source_uuid

    try:
        bundle = VLMObservationsBundle.model_validate(parsed)
    except ValidationError as exc:
        raise VLMClientError(f"VLM output failed schema validation: {exc}") from exc

    return _validate_bundle(bundle, source_uuid)


def _validate_bundle(bundle: VLMObservationsBundle, source_uuid: str) -> VLMObservationsBundle:
    """Structured output validator: catch and auto-correct logical inconsistencies.

    Rules checked:
    1. confidence >= 0.9 but zero Hazard observations → downgrade avg confidence
    2. Hazard present but zero Constraint (action) observations → inject a placeholder
    3. All high-confidence observations but zero uncertainties → inject a missing_data flag
    """
    import logging
    log = logging.getLogger(__name__)

    obs = list(bundle.observations)
    unc = list(bundle.uncertainties)
    hazards = [o for o in obs if o.type == "Hazard"]
    constraints = [o for o in obs if o.type == "Constraint"]
    avg_conf = sum(o.confidence for o in obs) / len(obs) if obs else 0.0
    changed = False

    # Rule 1: suspiciously high confidence with no hazards
    if avg_conf >= 0.90 and not hazards and obs:
        log.warning("Validator: avg_conf=%.2f but 0 hazards — capping confidences at 0.80", avg_conf)
        obs = [o.model_copy(update={"confidence": min(o.confidence, 0.80)}) for o in obs]
        changed = True

    # Rule 2: hazard present but no response-action constraints
    if hazards and not constraints:
        log.warning("Validator: %d hazard(s) but 0 Constraint obs — injecting placeholder action", len(hazards))
        obs.append(VLMObservation(
            entity="Safety team",
            type="Constraint",
            observation=(
                f"Contain and monitor the hazard identified near {hazards[0].entity}. "
                "Verify with additional sensor and camera feeds before dispatch."
            ),
            confidence=round(hazards[0].confidence * 0.85, 3),
        ))
        changed = True

    # Rule 3: observations present but no uncertainties — flag that validation was needed
    if obs and not unc:
        log.warning("Validator: %d obs but 0 uncertainties — injecting missing_data flag", len(obs))
        unc.append(VLMUncertainty(
            kind="missing_data",
            detail=(
                "No uncertainty flags were returned by the model for this bundle. "
                "At least one source angle may be inconclusive; recommend corroboration."
            ),
        ))
        changed = True

    if changed:
        return VLMObservationsBundle(
            source_uuid=source_uuid,
            observations=obs,
            uncertainties=unc,
        )
    return bundle
