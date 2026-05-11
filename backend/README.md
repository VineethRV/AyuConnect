# AyuConnect backend

FastAPI service that drives Gemma 4 on the device of your choice.

## Run

```bash
python -m venv .venv
source .venv/bin/activate          # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

By default the backend talks to a local Ollama at `http://localhost:11434`. Pull
the model once:

```bash
ollama pull gemma4:e4b
```

## Environment

| Variable | Default | Effect |
|---|---|---|
| `AYU_BACKEND` | `ollama` | One of `ollama`, `transformers`, `vllm`. |
| `AYU_MODEL_ID` | `google/gemma-4-E4B-it` | HF-style model id; mapped to Ollama tags automatically. |
| `AYU_OLLAMA_HOST` | `http://localhost:11434` | Ollama HTTP endpoint. |
| `AYU_VLLM_BASE_URL` | `http://localhost:8000/v1` | vLLM OpenAI-compatible endpoint. |
| `AYU_TEMPERATURE` | `0.4` | Sampling temperature. |
| `AYU_MAX_NEW_TOKENS` | `768` | Hard cap per turn. |
| `AYU_TOOL_LOOP_BUDGET` | `4` | Max tool calls in a single intake turn. |

## Endpoints

* `POST /chat` — patient intake turn. Multimodal (`image_b64`, `audio_b64`).
* `POST /report` — doctor-side SOAP draft over a transcript.
* `POST /triage` — standalone urgency classifier.
* `GET /health` — current backend + model id.

OpenAPI docs at `http://localhost:8000/docs`.

## Tests

```bash
python -m pytest tests/ -v
```

15 tests cover the offline tool layer and the chat tool-loop with a scripted
Gemma client (no live model required).
