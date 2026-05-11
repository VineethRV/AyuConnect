"""Function-calling tools exposed to Gemma 4.

Every tool is **fully offline** — the only data source is a small JSON knowledge
base shipped with the backend. This is deliberate: the hackathon brief asks for
solutions that work in low-bandwidth and privacy-sensitive contexts, so no tool
should silently hit the public internet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config import get_settings


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_KB: dict[str, Any] | None = None


def _kb() -> dict[str, Any]:
    global _KB
    if _KB is None:
        path = Path(__file__).resolve().parent / "data" / "medical_kb.json"
        if not path.exists():
            path = Path(get_settings().kb_path)
        _KB = json.loads(path.read_text(encoding="utf-8"))
    return _KB


# --------------------------------------------------------------------------- #
# Tool handlers — pure functions over the local KB.
# --------------------------------------------------------------------------- #


def _lookup_disease(name: str) -> dict[str, Any]:
    needle = name.strip().lower()
    for d in _kb()["diseases"]:
        if needle in d["name"].lower() or d["name"].lower() in needle:
            return d
    return {"name": name, "found": False, "message": "No entry in local KB."}


def _check_drug_interactions(medications: list[str]) -> dict[str, Any]:
    meds = {m.strip().lower() for m in medications if m and m.strip()}
    hits = []
    for entry in _kb()["interactions"]:
        a, b = (entry["pair"][0].lower(), entry["pair"][1].lower())
        if a in meds and b in meds:
            hits.append(entry)
    return {"interactions": hits, "checked": sorted(meds)}


_RED_FLAGS = {
    "chest pain", "crushing chest pain", "shortness of breath at rest",
    "stroke", "slurred speech", "facial droop", "one-sided weakness",
    "anaphylaxis", "throat swelling", "heavy bleeding", "uncontrolled bleeding",
    "loss of consciousness", "suicidal", "self harm", "self-harm",
    "blue lips", "cyanosis", "spo2 below 92", "rigid abdomen",
}

_YELLOW_FLAGS = {
    "fever > 39", "persistent vomiting", "dehydration",
    "severe pain", "fainting", "confusion", "blood in stool",
    "blood in urine", "rash spreading", "shortness of breath on exertion",
}


def _triage_severity(symptoms: list[str], age: int | None = None,
                     vitals: dict[str, float] | None = None) -> dict[str, Any]:
    text = " ".join(s.lower() for s in symptoms)
    red = [f for f in _RED_FLAGS if f in text]
    yellow = [f for f in _YELLOW_FLAGS if f in text]

    if vitals:
        spo2 = vitals.get("spo2")
        sbp = vitals.get("sbp")
        hr = vitals.get("hr")
        rr = vitals.get("rr")
        if spo2 is not None and spo2 < 92:
            red.append(f"SpO2 {spo2}% < 92%")
        if sbp is not None and sbp < 90:
            red.append(f"SBP {sbp} < 90")
        if rr is not None and rr > 30:
            red.append(f"RR {rr} > 30")
        if hr is not None and hr > 130:
            yellow.append(f"HR {hr} > 130")

    if age is not None and age >= 65 and yellow:
        # Elderly + any yellow flag → upgrade to yellow at minimum
        pass

    if red:
        return {"urgency": "red", "reason": "Red-flag symptoms detected.", "flags": red}
    if yellow:
        return {"urgency": "yellow", "reason": "Concerning symptoms — needs same-day review.", "flags": yellow}
    return {"urgency": "green", "reason": "No red/yellow flags identified — routine follow-up appropriate.", "flags": []}


def _recommend_specialist(diseases: list[str]) -> dict[str, Any]:
    matches = []
    for name in diseases:
        info = _lookup_disease(name)
        if info.get("specialty"):
            matches.append({"disease": info["name"], "specialty": info["specialty"]})
    if not matches:
        return {"specialty": "General Medicine", "matches": []}
    # Most common specialty wins
    from collections import Counter
    primary = Counter(m["specialty"] for m in matches).most_common(1)[0][0]
    return {"specialty": primary, "matches": matches}


def _search_local_kb(query: str, k: int = 3) -> dict[str, Any]:
    needle = query.lower()
    scored = []
    for d in _kb()["diseases"]:
        blob = (d["name"] + " " + d["summary"] + " " + " ".join(d["common_symptoms"])).lower()
        # crude term-overlap score
        score = sum(1 for term in needle.split() if term and term in blob)
        if score:
            scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    return {"results": [d for _, d in scored[:k]]}


def _submit_diagnosis_report(
    top_diseases: list[str],
    symptoms: list[str],
    urgency: str,
    urgency_reason: str,
    recommended_specialty: str,
    follow_up_in_days: int,
    drug_interactions: list[str] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Marks the intake as complete and returns the structured report."""
    return {
        "report": {
            "top_diseases": top_diseases,
            "symptoms": symptoms,
            "urgency": urgency,
            "urgency_reason": urgency_reason,
            "recommended_specialty": recommended_specialty,
            "follow_up_in_days": follow_up_in_days,
            "drug_interactions": drug_interactions or [],
            "notes": notes,
        },
        "final": True,
    }


# --------------------------------------------------------------------------- #
# Tool registry.
# --------------------------------------------------------------------------- #

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            name="lookup_disease",
            description="Look up a disease in the local offline medical knowledge base. Returns ICD-10, common symptoms, red flags, first-line treatments and recommended specialty.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Disease name."},
                },
                "required": ["name"],
            },
            handler=_lookup_disease,
        ),
        Tool(
            name="check_drug_interactions",
            description="Check the patient's medication list against a local interaction table. Returns interacting pairs with severity.",
            parameters={
                "type": "object",
                "properties": {
                    "medications": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Generic names of current medications.",
                    },
                },
                "required": ["medications"],
            },
            handler=_check_drug_interactions,
        ),
        Tool(
            name="triage_severity",
            description="Classify symptom urgency as red (emergency), yellow (same-day), or green (routine). Use early in the conversation if any concerning symptom is mentioned.",
            parameters={
                "type": "object",
                "properties": {
                    "symptoms": {"type": "array", "items": {"type": "string"}},
                    "age": {"type": "integer"},
                    "vitals": {
                        "type": "object",
                        "description": "Optional vitals (spo2, sbp, hr, rr).",
                    },
                },
                "required": ["symptoms"],
            },
            handler=_triage_severity,
        ),
        Tool(
            name="recommend_specialist",
            description="Given the top candidate diseases, recommend the most appropriate medical specialty for follow-up.",
            parameters={
                "type": "object",
                "properties": {
                    "diseases": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["diseases"],
            },
            handler=_recommend_specialist,
        ),
        Tool(
            name="search_local_kb",
            description="Free-text search over the local medical knowledge base. Useful when the patient's symptoms don't match an obvious named condition.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 3},
                },
                "required": ["query"],
            },
            handler=_search_local_kb,
        ),
        Tool(
            name="submit_diagnosis_report",
            description="Finalise the intake. Call this exactly once when you have enough information. After this, stop asking questions.",
            parameters={
                "type": "object",
                "properties": {
                    "top_diseases": {"type": "array", "items": {"type": "string"}, "description": "Up to 3 most likely conditions, most likely first."},
                    "symptoms": {"type": "array", "items": {"type": "string"}},
                    "urgency": {"type": "string", "enum": ["red", "yellow", "green"]},
                    "urgency_reason": {"type": "string"},
                    "recommended_specialty": {"type": "string"},
                    "follow_up_in_days": {"type": "integer", "description": "0 = emergency now, 1 = today, 7 = within a week, etc."},
                    "drug_interactions": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
                "required": ["top_diseases", "symptoms", "urgency", "urgency_reason", "recommended_specialty", "follow_up_in_days"],
            },
            handler=_submit_diagnosis_report,
        ),
    ]
}


def tool_schemas() -> list[dict[str, Any]]:
    return [t.schema() for t in TOOLS.values()]


def invoke_tool(name: str, arguments: dict[str, Any]) -> Any:
    if name not in TOOLS:
        return {"error": f"unknown tool: {name}"}
    try:
        return TOOLS[name].handler(**arguments)
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}
