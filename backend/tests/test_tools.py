"""Offline tests for the function-calling tool layer.

These don't touch Gemma — they pin the behaviour of the KB-backed handlers so a
broken edit doesn't silently change the medical guidance the model is grounded
in.
"""

from __future__ import annotations

from backend.app.tools import TOOLS, invoke_tool, tool_schemas


def test_tool_schemas_have_required_shape() -> None:
    schemas = tool_schemas()
    names = {s["function"]["name"] for s in schemas}
    assert names == set(TOOLS)
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "parameters" in s["function"]


def test_lookup_disease_known() -> None:
    out = invoke_tool("lookup_disease", {"name": "Asthma exacerbation"})
    assert out["icd10"] == "J45.9"
    assert "salbutamol inhaler" in [t.lower() for t in out["first_line_treatments"]]


def test_lookup_disease_unknown() -> None:
    out = invoke_tool("lookup_disease", {"name": "Phlebotinum poisoning"})
    assert out.get("found") is False


def test_drug_interaction_flagged() -> None:
    out = invoke_tool("check_drug_interactions",
                      {"medications": ["aspirin", "warfarin", "vitamin c"]})
    assert any(set(i["pair"]) == {"aspirin", "warfarin"} for i in out["interactions"])


def test_triage_red_flag() -> None:
    out = invoke_tool("triage_severity",
                      {"symptoms": ["crushing chest pain", "sweating"], "age": 58})
    assert out["urgency"] == "red"


def test_triage_yellow_flag() -> None:
    out = invoke_tool("triage_severity",
                      {"symptoms": ["persistent vomiting", "dehydration"]})
    assert out["urgency"] == "yellow"


def test_triage_green() -> None:
    out = invoke_tool("triage_severity", {"symptoms": ["mild cough", "runny nose"]})
    assert out["urgency"] == "green"


def test_triage_vitals_override() -> None:
    out = invoke_tool(
        "triage_severity",
        {"symptoms": ["fever"], "vitals": {"spo2": 88}},
    )
    assert out["urgency"] == "red"


def test_recommend_specialist() -> None:
    out = invoke_tool("recommend_specialist",
                      {"diseases": ["Asthma exacerbation", "Migraine"]})
    assert out["specialty"] in {"Pulmonology", "Neurology"}


def test_submit_report_returns_final() -> None:
    out = invoke_tool("submit_diagnosis_report", {
        "top_diseases": ["Type 2 Diabetes Mellitus"],
        "symptoms": ["polyuria", "polydipsia"],
        "urgency": "yellow",
        "urgency_reason": "Newly elevated glucose markers warrant same-day review.",
        "recommended_specialty": "Endocrinology",
        "follow_up_in_days": 1,
    })
    assert out["final"] is True
    assert out["report"]["urgency"] == "yellow"
