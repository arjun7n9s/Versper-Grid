from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    confidence: float
    backend: str


def transcribe_audio(path: Path, fallback_text: str = "") -> TranscriptResult:
    """Transcribe audio with faster-whisper when available.

    The demo must keep running on machines without STT dependencies, so a
    provided fallback transcript is returned explicitly as degraded mode.
    """
    model_name = os.environ.get("STT_MODEL", "base.en")
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(
            model_name,
            device=os.environ.get("STT_DEVICE", "cpu"),
            compute_type=os.environ.get("STT_COMPUTE_TYPE", "int8"),
        )
        segments, info = model.transcribe(str(path), beam_size=1, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        confidence = 0.86 if text else 0.0
        if text:
            return TranscriptResult(text=text, confidence=confidence, backend=f"faster-whisper:{model_name}")
        if fallback_text:
            return TranscriptResult(text=fallback_text, confidence=0.62, backend="fallback-empty-stt")
        return TranscriptResult(text="", confidence=0.0, backend=f"faster-whisper:{model_name}")
    except Exception:
        if fallback_text:
            return TranscriptResult(text=fallback_text, confidence=0.61, backend="fallback-transcript")
        label = path.stem.replace("_", " ").replace("-", " ")
        return TranscriptResult(
            text=f"Audio received from {label}; transcription backend unavailable.",
            confidence=0.35,
            backend="stt-unavailable",
        )
