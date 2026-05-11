"""End-to-end test of the chat tool-loop with a stub Gemma 4.

We don't have an Ollama server in CI, so we monkey-patch the gemma_client to
return a scripted sequence of responses. This locks in the orchestration logic
in ``routes/chat.py``: tool-calls are dispatched, results fed back, and a final
summary is returned when ``submit_diagnosis_report`` resolves.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import gemma_client
from backend.app.main import app


class _ScriptedClient:
    def __init__(self, scripts):
        self._scripts = list(scripts)

    async def __call__(self, **kwargs):
        if not self._scripts:
            return gemma_client.GemmaResponse(content="(scripted end)")
        nxt = self._scripts.pop(0)
        return nxt


@pytest.fixture
def client(monkeypatch):
    return TestClient(app)


def _stub(monkeypatch, scripts):
    sc = _ScriptedClient(scripts)
    monkeypatch.setattr(gemma_client, "generate", sc)


def test_simple_reply_no_tools(monkeypatch, client):
    _stub(monkeypatch, [
        gemma_client.GemmaResponse(content="How long have you had the headache?"),
    ])
    r = client.post("/chat", json={
        "history": [],
        "user_message": "I have a headache.",
        "patient_age": 30,
        "patient_sex": "F",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assistant_message"].startswith("How long")
    assert body["final"] is False
    assert body["summary"] is None


def test_tool_call_then_followup(monkeypatch, client):
    _stub(monkeypatch, [
        gemma_client.GemmaResponse(
            content="Let me check urgency.",
            tool_calls=[gemma_client.ToolCall(id="c1", name="triage_severity",
                                              arguments={"symptoms": ["crushing chest pain", "sweating"], "age": 60})],
        ),
        gemma_client.GemmaResponse(content="This is an emergency — please call an ambulance now."),
    ])
    r = client.post("/chat", json={
        "history": [],
        "user_message": "Crushing chest pain with sweating",
        "patient_age": 60,
    })
    body = r.json()
    assert r.status_code == 200
    assert any(tc["name"] == "triage_severity" for tc in body["tool_calls"])
    assert body["tool_calls"][0]["result"]["urgency"] == "red"
    assert "emergency" in body["assistant_message"].lower() or "ambulance" in body["assistant_message"].lower()


def test_final_summary_when_report_submitted(monkeypatch, client):
    submit_args = {
        "top_diseases": ["Type 2 Diabetes Mellitus", "Hypertension"],
        "symptoms": ["polyuria", "polydipsia", "fatigue"],
        "urgency": "yellow",
        "urgency_reason": "Newly suspected diabetes with osmotic symptoms.",
        "recommended_specialty": "Endocrinology",
        "follow_up_in_days": 2,
        "drug_interactions": [],
        "notes": "Refer for HbA1c and fasting glucose.",
    }
    _stub(monkeypatch, [
        gemma_client.GemmaResponse(
            content="Submitting your intake.",
            tool_calls=[gemma_client.ToolCall(id="c2", name="submit_diagnosis_report", arguments=submit_args)],
        ),
        gemma_client.GemmaResponse(content="Thanks — a clinician will review your case shortly."),
    ])
    r = client.post("/chat", json={
        "history": [
            {"role": "assistant", "content": "How long?"},
            {"role": "user", "content": "Three weeks."},
        ],
        "user_message": "I'm also losing weight.",
    })
    body = r.json()
    assert r.status_code == 200, r.text
    assert body["final"] is True
    assert body["summary"]["urgency"] == "yellow"
    assert "Type 2 Diabetes Mellitus" in body["summary"]["top_diseases"]


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_triage_endpoint(client):
    r = client.post("/triage", json={"symptoms": ["loss of consciousness"], "age": 70})
    assert r.status_code == 200
    body = r.json()
    assert body["urgency"] == "red"
    assert any("loss of consciousness" in flag for flag in body["red_flags"])
