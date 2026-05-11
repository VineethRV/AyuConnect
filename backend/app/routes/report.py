"""Doctor-facing endpoint: turn an intake transcript into a structured report.

This is non-streaming and synchronous — doctors want one canonical artefact, not
a chat. We re-use the chat tool-loop with the doctor-review system prompt so
the same Gemma 4 model can act in both modes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import gemma_client
from ..config import get_settings
from ..prompts import DOCTOR_REVIEW_SYSTEM
from ..schemas import ToolInvocation
from ..tools import invoke_tool, tool_schemas

router = APIRouter(prefix="/report", tags=["report"])


class ReportRequest(BaseModel):
    transcript: list[dict[str, str]] = Field(..., description="Patient-AI intake transcript.")
    doctor_question: str = Field("Please draft the consultation note.",
                                 description="What the doctor wants from the model right now.")


class ReportResponse(BaseModel):
    note: str
    tool_calls: list[ToolInvocation] = Field(default_factory=list)


@router.post("", response_model=ReportResponse)
async def report(req: ReportRequest) -> ReportResponse:
    settings = get_settings()
    msgs: list[dict[str, Any]] = [{"role": "system", "content": DOCTOR_REVIEW_SYSTEM}]
    transcript_text = "\n".join(f"{t['role']}: {t['content']}" for t in req.transcript)
    msgs.append({"role": "user", "content": f"Patient intake transcript:\n{transcript_text}\n\nDoctor: {req.doctor_question}"})

    invoked: list[ToolInvocation] = []
    tools = tool_schemas()

    for _ in range(settings.tool_loop_budget + 1):
        try:
            resp = await gemma_client.generate(messages=msgs, tools=tools)
        except gemma_client.GemmaError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        if not resp.tool_calls:
            return ReportResponse(note=resp.content, tool_calls=invoked)

        msgs.append({
            "role": "assistant",
            "content": resp.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in resp.tool_calls
            ],
        })
        for tc in resp.tool_calls:
            result = invoke_tool(tc.name, tc.arguments)
            invoked.append(ToolInvocation(name=tc.name, arguments=tc.arguments, result=result))
            msgs.append({"role": "tool", "tool_call_id": tc.id, "name": tc.name,
                         "content": str(result)})

    return ReportResponse(note="(report drafting exceeded reasoning budget)", tool_calls=invoked)
