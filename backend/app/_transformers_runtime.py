"""Transformers-backed Gemma 4 runtime.

Lives in its own module so importing the backend doesn't drag in torch unless
the user actually picked the ``transformers`` backend (Kaggle notebook path).
The module is intentionally lazy — model and processor load on first use.
"""

from __future__ import annotations

import base64
import io
import json
import re
import uuid
from typing import Any

from .gemma_client import GemmaError, GemmaResponse, ToolCall

_model = None
_processor = None


def _load(settings):
    global _model, _processor
    if _model is not None and _processor is not None:
        return _model, _processor

    try:
        import torch  # noqa: F401
        from transformers import AutoProcessor
        try:
            from transformers import AutoModelForMultimodalLM as _Model
        except ImportError:
            from transformers import AutoModelForCausalLM as _Model
    except ImportError as exc:
        raise GemmaError(
            "transformers backend requires `transformers`, `torch`, `accelerate`. "
            "Install with: pip install transformers torch accelerate Pillow soundfile"
        ) from exc

    _model = _Model.from_pretrained(settings.model_id, device_map="auto")
    _processor = AutoProcessor.from_pretrained(settings.model_id)
    return _model, _processor


def _to_pil(image_b64: str):
    from PIL import Image
    return Image.open(io.BytesIO(base64.b64decode(image_b64))).convert("RGB")


def _hydrate_media(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-style image_url/input_audio parts to Gemma processor parts."""
    out = []
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            new_parts = []
            for p in c:
                t = p.get("type")
                if t == "text":
                    new_parts.append({"type": "text", "text": p["text"]})
                elif t == "image_url":
                    url = p["image_url"]["url"]
                    b64 = url.split(",", 1)[1] if url.startswith("data:") else url
                    new_parts.append({"type": "image", "image": _to_pil(b64)})
                elif t == "input_audio":
                    import soundfile as sf
                    import numpy as np  # noqa: F401
                    audio_b64 = p["input_audio"]["data"]
                    data, sr = sf.read(io.BytesIO(base64.b64decode(audio_b64)))
                    new_parts.append({"type": "audio", "audio": data, "sampling_rate": sr})
                else:
                    new_parts.append(p)
            out.append({**m, "content": new_parts})
        else:
            out.append(m)
    return out


_TOOL_CALL_RE = re.compile(r"call:(?P<name>[A-Za-z_][A-Za-z0-9_]*)\{(?P<body>[^}]*)\}")


def _parse_tool_calls(text: str) -> tuple[str, list[ToolCall]]:
    """Best-effort parser for Gemma 4 native tool-call syntax.

    Gemma 4 emits ``call:name{k:v,k:v}``. ``processor.parse_response`` is
    preferred when available, but we keep this fallback for stability.
    """
    calls: list[ToolCall] = []
    cleaned_chunks = []
    last = 0
    for m in _TOOL_CALL_RE.finditer(text):
        cleaned_chunks.append(text[last:m.start()])
        name = m.group("name")
        body = m.group("body").strip()
        args: dict[str, Any] = {}
        if body:
            # Try JSON first (some templates emit valid JSON-ish bodies)
            try:
                args = json.loads("{" + body + "}")
            except Exception:
                # Fallback: k:v pairs separated by commas
                for pair in body.split(","):
                    if ":" not in pair:
                        continue
                    k, v = pair.split(":", 1)
                    args[k.strip()] = _coerce(v.strip())
        calls.append(ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=args))
        last = m.end()
    cleaned_chunks.append(text[last:])
    return "".join(cleaned_chunks).strip(), calls


def _coerce(val: str) -> Any:
    if val.startswith("[") and val.endswith("]"):
        try:
            return json.loads(val.replace("'", '"'))
        except Exception:
            return [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
    if val in {"true", "false"}:
        return val == "true"
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val.strip("'\"")


def run(*, messages, tools, settings) -> GemmaResponse:
    import torch

    model, processor = _load(settings)
    hydrated = _hydrate_media(messages)

    apply_kwargs = dict(
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    )
    if tools:
        apply_kwargs["tools"] = tools

    inputs = processor.apply_chat_template(hydrated, **apply_kwargs).to(model.device)

    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=settings.max_new_tokens,
            do_sample=settings.temperature > 0,
            temperature=max(settings.temperature, 1e-3),
        )

    input_len = inputs["input_ids"].shape[-1]
    generated = out[0][input_len:]
    text = processor.decode(generated, skip_special_tokens=True)

    # Prefer the official parser when available
    parsed = None
    if hasattr(processor, "parse_response"):
        try:
            parsed = processor.parse_response(text)
        except Exception:
            parsed = None

    if parsed and isinstance(parsed, dict):
        content = parsed.get("content", "") or ""
        calls: list[ToolCall] = []
        for tc in parsed.get("tool_calls") or []:
            calls.append(ToolCall(
                id=f"call_{uuid.uuid4().hex[:8]}",
                name=tc.get("name", ""),
                arguments=tc.get("arguments") or {},
            ))
        if calls or content:
            return GemmaResponse(content=content.strip(), tool_calls=calls)

    cleaned, calls = _parse_tool_calls(text)
    return GemmaResponse(content=cleaned, tool_calls=calls)
