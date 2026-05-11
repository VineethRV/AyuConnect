"""Stand-alone triage endpoint — exposes the same offline triage tool over HTTP.

Useful for the doctor portal's quick-check view and for callers who don't want
to run the full conversational loop.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import TriageRequest, TriageResponse
from ..tools import invoke_tool

router = APIRouter(prefix="/triage", tags=["triage"])


@router.post("", response_model=TriageResponse)
async def triage(req: TriageRequest) -> TriageResponse:
    result = invoke_tool(
        "triage_severity",
        {"symptoms": req.symptoms, "age": req.age, "vitals": req.vitals},
    )
    return TriageResponse(
        urgency=result.get("urgency", "green"),
        reason=result.get("reason", ""),
        red_flags=result.get("flags", []),
    )
