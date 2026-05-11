"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class ChatRequest(BaseModel):
    """Free-form multimodal chat turn.

    `image_b64` and `audio_b64` are base64-encoded payloads (no data: prefix).
    The frontend always sends history so the backend stays stateless — important
    for horizontal scaling and for replaying conversations during review.
    """

    history: list[ChatTurn] = Field(default_factory=list)
    user_message: str
    image_b64: str | None = None
    image_mime: str | None = None
    audio_b64: str | None = None
    audio_mime: str | None = None
    patient_age: int | None = None
    patient_sex: str | None = None


class ToolInvocation(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: Any


class ChatResponse(BaseModel):
    assistant_message: str
    tool_calls: list[ToolInvocation] = Field(default_factory=list)
    final: bool = False
    summary: "DiagnosisSummary | None" = None


class DiagnosisSummary(BaseModel):
    top_diseases: list[str]
    symptoms: list[str]
    urgency: Literal["red", "yellow", "green"]
    urgency_reason: str
    recommended_specialty: str
    follow_up_in_days: int
    drug_interactions: list[str] = Field(default_factory=list)
    notes: str = ""


class TriageRequest(BaseModel):
    symptoms: list[str]
    age: int | None = None
    sex: str | None = None
    vitals: dict[str, float] | None = None


class TriageResponse(BaseModel):
    urgency: Literal["red", "yellow", "green"]
    reason: str
    red_flags: list[str] = Field(default_factory=list)


ChatResponse.model_rebuild()
