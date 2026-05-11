# Kaggle submission map · AyuConnect

This file maps the AyuConnect repo to the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) submission checklist so a reviewer can find every required artefact in under 60 seconds.

## Required artefacts → where they live

| Required | Lives at |
|---|---|
| Public write-up | `README.md` (overview) and `docs/writeup.md` (technical depth) |
| Public code repository | https://github.com/VineethRV/AyuConnect (this repo) |
| Public Kaggle notebook | `notebooks/gemma4_ayuconnect_demo.ipynb` — upload to Kaggle, attach Gemma 4 weights as a model input |
| Demo files / working demo | `docker compose up` brings up the full stack; also `scripts/demo.py` for a CLI walk-through |
| Public video | Shoot using `docs/demo_script.md` (≤3 minutes, target 2:45) |
| Open-source licence | `LICENSE` — Apache 2.0 (matches Gemma 4 itself) |
| Cover image / media | Suggested: a screenshot of the patient intake with the green-banner summary, and one of the red-banner emergency triage. Both reproducible from the demo script. |

## Judging dimensions → strongest evidence

| Dimension | Where to look |
|---|---|
| **Impact & Vision** | `README.md` § "Why this fits the hackathon brief"; `docs/writeup.md` § 1 ("The problem") and § 2 ("Design"). |
| **Technical Depth & Execution** | `backend/app/gemma_client.py` (unified three-backend client), `backend/app/routes/chat.py` (tool-loop), `backend/app/_transformers_runtime.py` (multimodal media hydration + tool-call parsing), `backend/tests/` (15 tests, all passing). |
| **Video Pitch & Storytelling** | `docs/demo_script.md` — shot-by-shot script with explicit framing ("airplane mode badge visible at least twice"). |

## Gemma 4 integration expectations → coverage

The hackathon overview lists five expectations on the Gemma 4 side:

| Expectation | How AyuConnect demonstrates it |
|---|---|
| **Local / on-device functionality** | Default backend is Ollama at `localhost:11434`. Frontend talks to backend at `localhost:8000`. No network egress required for an intake. |
| **Multimodal capabilities** | Image upload + voice recording in the patient UI; `_transformers_runtime._hydrate_media` translates browser-side base64 payloads into Gemma 4's processor parts. |
| **Function calling / tool use** | Six tools defined in `backend/app/tools.py`; native tool-call loop in `backend/app/routes/chat.py`; output parsed via `processor.parse_response` in the Transformers path, native `tool_calls` field in Ollama and vLLM paths. |
| **Domain-specific fine-tuning potential** | Documented as future work in `docs/writeup.md` § 5 — the repo deliberately ships off-the-shelf weights to show how far structured prompting + tool grounding takes you. |
| **Edge deployment** | `docker compose up` runs on a laptop; `gemma4:e4b` is ~3 GB and runs on CPU; `AYU_BACKEND=vllm` switch enables shared-cluster deployments. |

## Track selection

**Health & Sciences.** Justified in `docs/writeup.md` § 1.

## Submitter

Vineeth Rao — `vineethrao.cs23@rvce.edu.in`
