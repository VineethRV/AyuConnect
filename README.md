# AyuConnect — Gemma 4 powered medical intake

> **Submission for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) · Health & Sciences track · May 2026.**

AyuConnect is a privacy-first, offline-capable medical intake assistant for clinics with limited connectivity or strict data-residency requirements. Patients describe symptoms by **text, voice, or photo**; Gemma 4 conducts a focused intake; the model **calls deterministic tools** to triage urgency, look up ICD-10 codes, and check drug interactions against a fully offline knowledge base; and a clinician receives a structured handoff with full transparency over every tool the model called.

**Nothing leaves the device.** The frontend never talks to a cloud LLM. The backend can drive Gemma 4 via Ollama on a laptop, Hugging Face Transformers on a workstation, or vLLM in a private datacentre — selected by a single environment variable.

---

## TL;DR — what's new vs. the original AyuConnect

| Before | After |
|---|---|
| Cloud Groq API (`llama3-8b-8192`), API key in repo | **Gemma 4** via Ollama / Transformers / vLLM, no third-party data egress |
| Text-only patient chat | **Text + image + voice** intake (Gemma 4 native multimodal) |
| Free-form prose summary | **Native function calling** with 6 grounded tools, structured `DiagnosisSummary` |
| No urgency triage | Red / yellow / green triage produced by a deterministic offline tool the model *must* call when red-flag symptoms appear |
| Doctor sees raw chat | Doctor sees an **AI-drafted SOAP note** with drug-interaction warnings, plus an audit trail of every tool call |
| In-browser Groq call from a Next.js client component | FastAPI backend with a unified Gemma 4 client + Pydantic schemas + 15 tests |

---

## Why this fits the hackathon brief

The brief asks for solutions that work **where infrastructure is lacking** — low bandwidth, no cloud connectivity, or strict privacy — and that use Gemma 4's three signature capabilities (local execution, multimodality, function calling). AyuConnect threads all three:

* **On-device.** Default backend is Ollama running on the clinic's own laptop. The frontend talks to it over `localhost`. Bandwidth required for a patient intake: **zero**.
* **Multimodal.** A community health worker can photograph a rash, an elderly patient can speak symptoms in their language, and a literate patient can type — Gemma 4 E4B handles all three natively in one model.
* **Function calling.** The model is *expected* to defer judgement to tools for any safety-critical decision (urgency triage, drug interactions, ICD-10 lookup). The tools run against a shipped JSON KB, so they're auditable and have no external dependencies.

---

## Architecture

```
┌────────────────────────┐   HTTP    ┌─────────────────────────────────────────┐
│  Next.js 14 frontend   │  ───────▶ │  FastAPI backend (Python)               │
│                        │           │                                         │
│  • patient intake UI   │           │  • /chat   — multimodal tool-loop       │
│  • image / voice input │           │  • /report — doctor-side SOAP draft     │
│  • tool-call panel     │           │  • /triage — standalone urgency check   │
│  • doctor portal       │           │                                         │
└────────────────────────┘           │  Gemma 4 client (one of:)               │
                                     │    ┌───────────────┐  ┌──────────────┐ │
                                     │    │ Ollama (local)│  │ Transformers │ │
                                     │    └───────────────┘  └──────────────┘ │
                                     │    ┌────────────────────────────────┐  │
                                     │    │ vLLM (OpenAI-compatible)       │  │
                                     │    └────────────────────────────────┘  │
                                     │                                         │
                                     │  Offline tools (over JSON medical KB):  │
                                     │   triage_severity / lookup_disease /    │
                                     │   check_drug_interactions /             │
                                     │   recommend_specialist / search_kb /    │
                                     │   submit_diagnosis_report               │
                                     └─────────────────────────────────────────┘
```

The Gemma 4 client is the same code regardless of backend — only the wire format adapter changes. That is what lets the project demo on a laptop (Ollama), reproduce in a Kaggle notebook (Transformers), and scale on a private cluster (vLLM) without forking.

---

## Quick start

### Option A — local laptop (default, no GPU required)

```bash
# 1. Pull Gemma 4 E4B into Ollama (~3 GB; one-time)
ollama pull gemma4:e4b

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate    # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd ../frontend
cp .env.example .env.local        # already points at localhost:8000
npm install
npm run dev                       # → http://localhost:3000
```

That's it. Open `http://localhost:3000`, click **Patient Portal → Get Diagnosis**, and start talking to Gemma 4.

### Option B — Kaggle GPU notebook

Run `notebooks/gemma4_ayuconnect_demo.ipynb` end-to-end on a Kaggle T4. The notebook loads `google/gemma-4-E4B-it` via Transformers and reproduces the full pipeline — text intake, image-grounded intake, audio intake, and doctor-side note drafting.

### Option C — vLLM on a private GPU server

```bash
python -m vllm.entrypoints.openai.api_server --model google/gemma-4-E4B-it
AYU_BACKEND=vllm AYU_MODEL_ID=google/gemma-4-E4B-it uvicorn backend.app.main:app
```

---

## The tool catalogue (offline grounding)

Every tool is a pure function over `backend/app/data/medical_kb.json`. No tool makes a network call.

| Tool | When the model calls it |
|---|---|
| `triage_severity` | Early in the conversation if any red-flag symptom is mentioned. Returns `red`/`yellow`/`green` with the specific flags that fired. |
| `lookup_disease` | When a candidate diagnosis emerges. Returns ICD-10, common symptoms, red flags, first-line treatments, recommended specialty. |
| `check_drug_interactions` | When the patient lists current medications. Flags severity-rated interacting pairs. |
| `recommend_specialist` | After the top-3 differential is clear. Aggregates per-disease specialties into one referral. |
| `search_local_kb` | When the symptoms don't match an obvious named condition. |
| `submit_diagnosis_report` | Exactly once, at the end. Produces the structured `DiagnosisSummary` the clinician reviews. |

All six tools and 5 chat-loop scenarios are pinned by automated tests — see `backend/tests/`.

---

## Hackathon judging dimensions — where to look

| Dimension | Evidence |
|---|---|
| **Impact & Vision** | `docs/writeup.md` (deployment story, target users), `README.md` (above). |
| **Technical Depth & Execution** | `backend/app/gemma_client.py` (three-backend abstraction), `backend/app/routes/chat.py` (tool-loop), `backend/app/tools.py` (offline KB grounding), `backend/tests/` (15 tests, all passing). |
| **Multimodality** | `frontend/app/get-diagnosis/get/page.tsx` (image + audio capture), `_transformers_runtime.py` (`_hydrate_media`), notebook sections 5 & 6. |
| **Function calling / tool use** | `backend/app/tools.py`, `backend/app/routes/chat.py`, notebook section 4. |
| **On-device / privacy** | Default Ollama backend, no telemetry, fully offline tools, `docs/writeup.md` § "Privacy posture". |
| **Video pitch** | `docs/demo_script.md`. |
| **Reproducibility** | `docker-compose.yml`, `notebooks/gemma4_ayuconnect_demo.ipynb`, pinned `backend/requirements.txt`. |

---

## Project layout

```
ayuconnect/
├── backend/                       FastAPI + Gemma 4 client
│   ├── app/
│   │   ├── main.py                FastAPI entrypoint
│   │   ├── config.py              env-driven backend selection
│   │   ├── schemas.py             Pydantic request/response models
│   │   ├── prompts.py             system prompts (intake + doctor)
│   │   ├── tools.py               function-calling tool registry
│   │   ├── gemma_client.py        unified Ollama / vLLM / Transformers client
│   │   ├── _transformers_runtime.py   lazy in-process model runtime
│   │   ├── routes/                /chat, /report, /triage
│   │   └── data/medical_kb.json   offline disease + interaction KB
│   ├── tests/                     15 tests (tools + chat tool-loop)
│   └── requirements.txt
├── frontend/                      Next.js 14 client
│   └── app/
│       ├── lib/api.ts             typed backend client
│       ├── get-diagnosis/get/     patient intake with image + voice
│       └── give-diagnosis/        doctor portal with AI note drafting
├── notebooks/
│   └── gemma4_ayuconnect_demo.ipynb       Kaggle submission notebook
├── scripts/
│   └── demo.py                    CLI walk-through for the video shoot
├── docs/
│   ├── writeup.md                 technical writeup
│   └── demo_script.md             video script
├── docker-compose.yml             one-command local deployment
└── LICENSE                        Apache 2.0
```

---

## Tests

```bash
cd backend
python -m pytest tests/ -v
# 15 passed in ~1s
```

The chat-loop tests stub the Gemma client with scripted responses so the orchestration logic is verified without needing a live model — that means the tests pass on CI and on a laptop without GPU.

Frontend:

```bash
cd frontend
npx tsc --noEmit            # zero type errors
```

---

## Safety posture

AyuConnect is an **intake assistant**, not a diagnostician. Three guardrails enforce that:

1. The intake system prompt forbids the model from claiming certainty about a diagnosis or prescribing medication; final judgement always sits with a human clinician.
2. Red-flag symptoms force the model into the `triage_severity` tool, which is a deterministic check the model cannot override — if `urgency=red`, the patient is told to seek emergency care immediately.
3. The doctor portal surfaces every tool the model called, with arguments and results, so the clinician can verify the AI's reasoning before accepting any draft note.

---

## License

Apache 2.0 — matching Gemma 4's own licence. See `LICENSE`.

## Acknowledgements

* Google DeepMind & the Gemma team for shipping a capable open multimodal model with native function calling.
* The original AyuConnect winning team at the RVCE GenAI hackathon for the seed concept this submission builds on.
