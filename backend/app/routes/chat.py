"""Chat endpoint: one turn of patient intake with the Gemma 4 tool-loop."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .. import gemma_client
from ..config import get_settings
from ..prompts import INTAKE_SYSTEM
from ..schemas import ChatRequest, ChatResponse, DiagnosisSummary, ToolInvocation
from ..tools import invoke_tool, tool_schemas

router = APIRouter(prefix="/chat", tags=["chat"])


def _build_messages(req: ChatRequest) -> list[dict[str, Any]]:
    """Materialise the conversation into OpenAI-style chat messages.

    The intake system prompt is always prepended fresh — never trust client-side
    history to include it correctly, since the client is just a browser and the
    prompt is a security boundary.
    """
    msgs: list[dict[str, Any]] = [{"role": "system", "content": INTAKE_SYSTEM}]
    if req.patient_age is not None or req.patient_sex is not None:
        meta_bits = []
        if req.patient_age is not None:
            meta_bits.append(f"age={req.patient_age}")
        if req.patient_sex:
            meta_bits.append(f"sex={req.patient_sex}")
        msgs.append({"role": "system", "content": f"Patient meta: {', '.join(meta_bits)}."})

    for t in req.history:
        if t.role == "system":
            # Already injected above — skip client-supplied system turns.
            continue
        msgs.append({"role": t.role, "content": t.content})

    msgs.append({"role": "user", "content": req.user_message})
    return msgs


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    settings = get_settings()
    messages = _build_messages(req)
    tools = tool_schemas()
    invoked: list[ToolInvocation] = []
    final_summary: DiagnosisSummary | None = None

    image_b64, image_mime = req.image_b64, req.image_mime
    audio_b64, audio_mime = req.audio_b64, req.audio_mime

    for _ in range(settings.tool_loop_budget + 1):
        try:
            resp = await gemma_client.generate(
                messages=messages,
                tools=tools,
                image_b64=image_b64,
                image_mime=image_mime,
                audio_b64=audio_b64,
                audio_mime=audio_mime,
            )
        except gemma_client.GemmaError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # Media is consumed by the first turn only — subsequent tool-loop turns
        # carry the conversation, not raw bytes.
        image_b64 = image_mime = None
        audio_b64 = audio_mime = None

        if not resp.tool_calls:
            return ChatResponse(
                assistant_message=resp.content,
                tool_calls=invoked,
                final=False,
                summary=None,
            )

        # Record the assistant's tool-calling turn in history so the model can
        # observe its own previous calls when planning the next one.
        messages.append({
            "role": "assistant",
            "content": resp.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in resp.tool_calls
            ],
        })

        for tc in resp.tool_calls:
            result = invoke_tool(tc.name, tc.arguments)
            invoked.append(ToolInvocation(name=tc.name, arguments=tc.arguments, result=result))
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.name,
                "content": _stringify(result),
            })
            if tc.name == "submit_diagnosis_report" and isinstance(result, dict):
                report = result.get("report") or {}
                final_summary = DiagnosisSummary(
                    top_diseases=report.get("top_diseases", []),
                    symptoms=report.get("symptoms", []),
                    urgency=report.get("urgency", "green"),
                    urgency_reason=report.get("urgency_reason", ""),
                    recommended_specialty=report.get("recommended_specialty", "General Medicine"),
                    follow_up_in_days=report.get("follow_up_in_days", 7),
                    drug_interactions=report.get("drug_interactions", []),
                    notes=report.get("notes", ""),
                )

        if final_summary is not None:
            # Let the model produce its closing patient-facing message after
            # `submit_diagnosis_report` resolves.
            closing = await gemma_client.generate(messages=messages, tools=tools)
            return ChatResponse(
                assistant_message=closing.content or "Thank you — your intake has been forwarded to a clinician.",
                tool_calls=invoked,
                final=True,
                summary=final_summary,
            )

    # Tool-loop budget exhausted — return whatever the model last produced.
    return ChatResponse(
        assistant_message="(intake exceeded reasoning budget — please rephrase or try again)",
        tool_calls=invoked,
        final=False,
        summary=None,
    )


def _stringify(value: Any) -> str:
    import json as _json
    if isinstance(value, str):
        return value
    try:
        return _json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)
