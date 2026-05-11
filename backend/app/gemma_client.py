"""Unified Gemma 4 client.

Three deployment paths, one interface:

    * **ollama**       — local on-device (`ollama serve`). Default. No GPU required.
    * **transformers** — Hugging Face Transformers (for Kaggle GPU notebook).
    * **vllm**         — OpenAI-compatible server (for shared clusters).

All three speak the same chat-completions shape: a list of messages where each
message may contain text, an inline image (base64), or audio (base64), plus an
optional `tool_calls` field on assistant messages and a matching `tool` role for
tool results.

The caller hands us:
    history          : list[dict] — already in OpenAI-style format
    tools            : list[dict] — JSON-schema tool definitions (from tools.py)
    image_b64/mime   : optional multimodal input
    audio_b64/mime   : optional multimodal input

We return:
    GemmaResponse(content, tool_calls)
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import Backend, get_settings


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class GemmaResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class GemmaError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #


async def generate(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    image_b64: str | None = None,
    image_mime: str | None = None,
    audio_b64: str | None = None,
    audio_mime: str | None = None,
) -> GemmaResponse:
    """Run one Gemma 4 completion across whichever backend is configured."""
    settings = get_settings()

    if image_b64 or audio_b64:
        # Multimodal content goes on the latest user message — that's where it
        # is referenced in the conversation flow.
        messages = _attach_media(messages, image_b64, image_mime, audio_b64, audio_mime, settings.backend)

    if settings.backend is Backend.OLLAMA:
        return await _ollama_chat(messages, tools, settings)
    if settings.backend is Backend.VLLM:
        return await _openai_chat(messages, tools, settings.vllm_base_url, settings.vllm_api_key, settings.model_id, settings)
    if settings.backend is Backend.TRANSFORMERS:
        return _transformers_chat(messages, tools, settings)
    raise GemmaError(f"unknown backend {settings.backend!r}")


# --------------------------------------------------------------------------- #
# Media attachment — different backends want different shapes.
# --------------------------------------------------------------------------- #


def _attach_media(
    messages: list[dict[str, Any]],
    image_b64: str | None,
    image_mime: str | None,
    audio_b64: str | None,
    audio_mime: str | None,
    backend: Backend,
) -> list[dict[str, Any]]:
    if not messages:
        raise GemmaError("cannot attach media — no messages")
    msgs = [dict(m) for m in messages]
    last = msgs[-1]
    if last.get("role") != "user":
        raise GemmaError("media must attach to a user turn")

    if backend is Backend.OLLAMA:
        # Ollama accepts `images: [base64,...]` on the message. Audio still
        # passes through as a content block when using gemma-4 (Ollama's
        # multimodal support evolves quickly; we fall back to a text marker if
        # audio is supplied but unsupported).
        if image_b64:
            last["images"] = [image_b64]
        if audio_b64:
            last.setdefault("audio", []).append(audio_b64)
        return msgs

    # OpenAI-compatible (vLLM) and Transformers both accept rich content lists.
    text = last.get("content")
    content_parts: list[dict[str, Any]] = []
    if isinstance(text, str) and text:
        content_parts.append({"type": "text", "text": text})
    elif isinstance(text, list):
        content_parts.extend(text)
    if image_b64:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{image_mime or 'image/png'};base64,{image_b64}"},
        })
    if audio_b64:
        content_parts.append({
            "type": "input_audio",
            "input_audio": {"data": audio_b64, "format": (audio_mime or "audio/wav").split("/")[-1]},
        })
    last["content"] = content_parts
    return msgs


# --------------------------------------------------------------------------- #
# Backend: Ollama
# --------------------------------------------------------------------------- #


async def _ollama_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    settings,
) -> GemmaResponse:
    body: dict[str, Any] = {
        "model": _ollama_model_tag(settings.model_id),
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": settings.max_new_tokens,
            "temperature": settings.temperature,
        },
    }
    if tools:
        body["tools"] = tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            r = await client.post(f"{settings.ollama_host}/api/chat", json=body)
        except httpx.HTTPError as exc:
            raise GemmaError(f"Ollama unreachable at {settings.ollama_host}: {exc}") from exc
        if r.status_code >= 400:
            raise GemmaError(f"Ollama error {r.status_code}: {r.text}")
        data = r.json()

    msg = data.get("message", {})
    content = msg.get("content", "") or ""
    tool_calls: list[ToolCall] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"_raw": args}
        tool_calls.append(ToolCall(
            id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
            name=fn.get("name", ""),
            arguments=args,
        ))
    return GemmaResponse(content=content, tool_calls=tool_calls)


def _ollama_model_tag(model_id: str) -> str:
    """Map HF-style IDs to Ollama tag conventions.

    HF says ``google/gemma-4-E4B-it``. Ollama tags use lowercase with size suffix:
    ``gemma4:e4b``. We accept either form and pass through anything that already
    looks like an Ollama tag.
    """
    if ":" in model_id and "/" not in model_id:
        return model_id
    lowered = model_id.lower()
    for size in ("e2b", "e4b", "26b-a4b", "31b"):
        if size in lowered:
            return f"gemma4:{size}"
    return "gemma4:e4b"


# --------------------------------------------------------------------------- #
# Backend: vLLM (OpenAI-compatible)
# --------------------------------------------------------------------------- #


async def _openai_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    base_url: str,
    api_key: str,
    model_id: str,
    settings,
) -> GemmaResponse:
    body: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "max_tokens": settings.max_new_tokens,
        "temperature": settings.temperature,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            r = await client.post(
                f"{base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        except httpx.HTTPError as exc:
            raise GemmaError(f"vLLM unreachable at {base_url}: {exc}") from exc
        if r.status_code >= 400:
            raise GemmaError(f"vLLM error {r.status_code}: {r.text}")
        data = r.json()

    choice = data["choices"][0]["message"]
    content = choice.get("content") or ""
    tool_calls: list[ToolCall] = []
    for tc in choice.get("tool_calls") or []:
        fn = tc["function"]
        args = fn.get("arguments") or "{}"
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"_raw": args}
        tool_calls.append(ToolCall(id=tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                                   name=fn["name"], arguments=args))
    return GemmaResponse(content=content, tool_calls=tool_calls)


# --------------------------------------------------------------------------- #
# Backend: Transformers (in-process)
# --------------------------------------------------------------------------- #


def _transformers_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    settings,
) -> GemmaResponse:
    from . import _transformers_runtime as rt  # local import — keeps Torch optional

    return rt.run(messages=messages, tools=tools or [], settings=settings)


# --------------------------------------------------------------------------- #
# Helpers used by routes when building the conversation
# --------------------------------------------------------------------------- #


def encode_image_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def encode_audio_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
