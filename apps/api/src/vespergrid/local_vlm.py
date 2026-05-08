"""Local Qwen2.5-VL-7B-Instruct inference via HuggingFace transformers.

Used when VLLM_BASE_URL is not set (local RTX 5060 / any CUDA GPU).
Falls back to CPU if no CUDA device is available (slow but functional).

Environment variables:
- VLM_MODEL_ID   default: Qwen/Qwen2.5-VL-7B-Instruct
- VLM_LOAD_4BIT  default: "1"  (bitsandbytes 4-bit NF4 quant; fits 8GB VRAM)
- VLM_DEVICE     default: "cuda" if available, else "cpu"
"""
from __future__ import annotations

import json
import logging
import os
from io import BytesIO
from typing import Iterable

from PIL import Image

from .vlm_client import VLMClientError, VLMObservationsBundle, _SYSTEM_PROMPT, _strip_json

logger = logging.getLogger(__name__)

_MODEL_ID = os.environ.get("VLM_MODEL_ID", "Qwen/Qwen2.5-VL-7B-Instruct")
_LOAD_4BIT = os.environ.get("VLM_LOAD_4BIT", "1") == "1"

_model = None
_processor = None


def _load() -> tuple:
    global _model, _processor
    if _model is not None:
        return _model, _processor

    import torch
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    device = os.environ.get("VLM_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Loading %s on %s (4bit=%s)", _MODEL_ID, device, _LOAD_4BIT)

    load_kwargs: dict = {
        "torch_dtype": "auto",
        "device_map": device,
    }
    if _LOAD_4BIT and device != "cpu":
        try:
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=__import__("torch").bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            load_kwargs.pop("torch_dtype", None)
            load_kwargs.pop("device_map", None)
        except ImportError:
            logger.warning("bitsandbytes not installed; loading in full precision")

    _processor = AutoProcessor.from_pretrained(_MODEL_ID)
    _model = Qwen2_5_VLForConditionalGeneration.from_pretrained(_MODEL_ID, **load_kwargs)
    if device != "cpu" and not _LOAD_4BIT:
        _model = _model.to(device)
    _model.eval()
    logger.info("Model loaded.")
    return _model, _processor


def _build_messages_local(
    source_uuid: str,
    field_notes: str,
    pil_images: list,
) -> list[dict]:
    content = []
    for img in pil_images:
        content.append({"type": "image", "image": img})
    content.append({
        "type": "text",
        "text": (
            f"source_uuid: {source_uuid}\n"
            f"operator_field_notes: {field_notes or '(none)'}\n"
            "Return the JSON now."
        ),
    })
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


async def parse_evidence_local(
    *,
    source_uuid: str,
    field_notes: str,
    image_payloads: Iterable[bytes],
    image_mime: str = "image/jpeg",
) -> VLMObservationsBundle:
    """Run Qwen2.5-VL locally via transformers. Blocking — run in executor."""
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _infer_sync,
        source_uuid,
        field_notes,
        list(image_payloads),
    )
    return result


def _infer_sync(
    source_uuid: str,
    field_notes: str,
    image_bytes_list: list[bytes],
) -> VLMObservationsBundle:
    from pydantic import ValidationError
    import torch

    max_frames = int(os.environ.get("VLM_MAX_FRAMES", "4"))
    image_bytes_list = image_bytes_list[:max_frames]

    pil_images = [Image.open(BytesIO(b)).convert("RGB") for b in image_bytes_list]

    model, processor = _load()
    messages = _build_messages_local(source_uuid, field_notes, pil_images)

    try:
        from qwen_vl_utils import process_vision_info
        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
    except ImportError:
        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = processor(
            text=[text],
            images=pil_images,
            return_tensors="pt",
        )

    device = next(model.parameters()).device
    inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}

    with __import__("torch").no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=768,
            do_sample=False,
            temperature=None,
            top_p=None,
        )
    generated = output_ids[:, inputs["input_ids"].shape[1]:]
    raw_text = processor.batch_decode(generated, skip_special_tokens=True)[0]

    cleaned = _strip_json(raw_text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise VLMClientError(
            f"Local VLM did not return valid JSON: {raw_text[:400]!r}"
        ) from exc

    parsed["source_uuid"] = source_uuid
    try:
        return VLMObservationsBundle.model_validate(parsed)
    except ValidationError as exc:
        raise VLMClientError(f"Local VLM output failed schema validation: {exc}") from exc
