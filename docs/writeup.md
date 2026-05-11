# AyuConnect technical writeup

> Submission for the Gemma 4 Good Hackathon · Health & Sciences track.
> Author contact: vineethrao.cs23@rvce.edu.in · Source: https://github.com/VineethRV/AyuConnect

## 1. The problem

In low- and middle-income countries a single primary-care doctor serves thousands of patients. A 2024 Lancet survey of rural Karnataka primary health centres found a median consultation time of **3 minutes 40 seconds**. In that window the doctor has to elicit the chief complaint, gather history, examine the patient, decide on investigations, and prescribe — frequently with no follow-up. The natural triage failures are:

* **Under-triage of emergencies**: a 58-year-old with crushing chest pain spends 90 minutes in the waiting room because the receptionist didn't recognise the symptom pattern.
* **Drug interactions missed**: a patient on warfarin is sent home with a new prescription for ibuprofen because the doctor didn't have the bandwidth to look up interactions.
* **Patient-side recall errors**: by the time the patient describes their symptoms to the doctor, they have already forgotten half of them.

A pre-consultation AI intake — done in the waiting room on a clinic-owned tablet — could prepare the case, surface red flags, and let the doctor spend their 3 minutes on the parts a human is uniquely suited for.

But for this to actually deploy at a rural PHC, the AI must satisfy three constraints that ruled out the prior wave of GPT-4-class telemedicine pilots:

1. **Works offline.** Mobile-data cost is real, and rural connectivity is bursty. The PHC can't depend on a cloud LLM.
2. **Patient data stays local.** India's DPDP Act and the EU's GDPR both make cross-border processing of health data a legal hazard. The PHC needs deployment patterns where the data is never sent to a third party.
3. **Multimodal input.** Many patients are not fluent typists; many describe symptoms vividly only when shown a photo of their wound.

Gemma 4 — Apache 2.0, runs on a laptop, multimodal, native function calling — is the first open model that hits all three at once. AyuConnect is the smallest thing we could build to prove it.

## 2. Design

### 2.1 Surface
AyuConnect has two surfaces:

* **Patient intake**: a chat that accepts text, images, and short voice notes. The patient meta (age, sex) is collected first; the intake prompt is then primed with that. Gemma 4 conducts ≤8 focused questions or fewer if red flags fire.
* **Doctor portal**: lists prepared intakes, lets the doctor ask Gemma 4 for a SOAP-style draft, and surfaces every tool the model called so the doctor can verify reasoning before accepting any wording.

### 2.2 Why function calling is the safety story
Telemedicine AIs that synthesise their answers free-form are unreviewable. AyuConnect uses Gemma 4's native function calling to force the model to route safety-critical decisions through deterministic offline tools:

* `triage_severity` returns `red`/`yellow`/`green` from a finite list of red-flag symptoms and vital-sign thresholds. The model **cannot** override its output.
* `check_drug_interactions` returns interacting pairs from a shipped JSON table with severity labels.
* `lookup_disease` returns canonical ICD-10 codes, red flags, and first-line treatments — the model uses this instead of hallucinating clinical knowledge.
* `submit_diagnosis_report` is the only way the intake terminates with a structured handoff — the model's free-text output without this call is treated as still-in-progress and isn't shown to the doctor.

Every tool call is recorded with its arguments and result and rendered in the UI under a "tool calls" disclosure. A clinician reviewing a Gemma 4-drafted note can verify: *did the model call `check_drug_interactions`? With which inputs? What did it get back?*

### 2.3 Why multimodal matters in this specific app
Two distinct accessibility pathways:

* **Photo upload** — a community health worker in a remote village photographs a child's rash. Gemma 4's vision encoder grounds the differential ("atopic dermatitis vs. impetigo"). Without vision, the worker would have to describe the rash in words, badly.
* **Voice input** — an elderly patient with low literacy speaks symptoms in their first language. Gemma 4 E4B has native audio understanding, so we don't need a separate ASR + translation stack. The model both transcribes and reasons.

These aren't gimmicks — they are the two modalities that ruled out text-only AI in actual deployment.

### 2.4 Deployment topologies the architecture supports
Same code, three deployment paths, switched by `AYU_BACKEND`:

| `AYU_BACKEND` | What runs Gemma 4 | Where this fits |
|---|---|---|
| `ollama` (default) | `ollama serve` on the same laptop as the backend | The on-the-laptop PHC scenario. Zero network. |
| `transformers` | In-process via Hugging Face Transformers | The Kaggle notebook; also a single-GPU workstation. |
| `vllm` | A vLLM OpenAI-compatible server | A district-hospital private cluster serving many clinics. |

`backend/app/gemma_client.py` is the entire abstraction layer — under 200 lines.

## 3. Implementation notes

* **Stateless backend.** The frontend sends history on every turn; the backend never stores PHI. This is what enables horizontal scaling later, and it means a misbehaving frontend can't leak old conversations.
* **Tool-loop budget.** The backend caps tool-loop depth at `AYU_TOOL_LOOP_BUDGET=4` so a model that gets stuck calling tools in a loop will return control to the user instead of burning compute.
* **Prompt as security boundary.** The system prompt is injected fresh by the backend on every call and any client-supplied `role=system` turn is filtered out. The browser cannot escalate its own privileges.
* **No telemetry.** The backend ships with no analytics, no error reporting, no third-party SDKs. Curl `localhost:11434` is the only external call any single intake makes.

## 4. What's in the repo, in priority order

1. `backend/app/gemma_client.py` + `backend/app/_transformers_runtime.py` — the three-backend Gemma 4 client. This is the part that most directly demonstrates fluency with Gemma 4's chat-template, multimodal inputs, and tool-call parsing.
2. `backend/app/routes/chat.py` — the tool-loop orchestration. Read this if you only have time to read one file.
3. `backend/app/tools.py` — the six offline tools. The thing the model is grounded in.
4. `frontend/app/get-diagnosis/get/page.tsx` — the patient intake UI, with image + voice + a tool-call transparency panel.
5. `notebooks/gemma4_ayuconnect_demo.ipynb` — the standalone reproduction. Runs end-to-end on a Kaggle T4.

## 5. Limitations & next steps

* The shipped knowledge base contains 10 diseases and 7 drug-interaction pairs — a deployment-ready KB would need a clinically-curated corpus (open candidates: ICD-10-CM, MedDRA, MIMS interaction tables).
* The model is intentionally **not** fine-tuned on medical conversations; we wanted to show how far structured prompting + tool grounding gets you with Gemma 4 off the shelf. A natural follow-up is a small LoRA on de-identified PHC dialogues to tighten the question style.
* The audio path is one-shot per turn; streaming audio would be a better fit for live intake but is gated on a different Gemma 4 deployment template.
* Frontend has no auth — that's intentional for the demo; a real deployment would gate the doctor portal behind clinic SSO.

## 6. Privacy posture (one paragraph)

Patient data is never transmitted outside the device or LAN the backend runs on. The default backend is `ollama`, which serves the model from `localhost:11434`. The frontend hits the FastAPI backend at `localhost:8000`. No third-party SDK ships with the project; no analytics; no telemetry. The repo includes no API keys to leak. To run the project, no account or credit-card is required on any service other than HuggingFace (to download Gemma 4 once; weights then live on disk).

That posture is the entire point — and it is uniquely enabled by a model the clinic can actually own.
