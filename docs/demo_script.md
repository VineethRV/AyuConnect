# AyuConnect — demo video script (≤3 minutes)

The Kaggle submission requires a short video. Below is the shot-by-shot script.
Total runtime target: **2:45**. Optimise for "what does it actually do, and why
is that hard without Gemma 4?"

---

## 0:00 — 0:15 · Cold open with the constraint

> Camera on a laptop in airplane mode, sitting on a wooden desk.
> Narrator: "This laptop has no internet. In the next two minutes it's going to
> conduct a medical intake — see a photo, listen to a voice note, triage an
> emergency, check drug interactions, and hand the case to a clinician. Every
> bit of compute happens on this machine. Nothing leaves it."

Cut to terminal: `ollama list` shows `gemma4:e4b`. Then `curl localhost:8000/health`
returns `{"backend":"ollama","model_id":"google/gemma-4-E4B-it"}`.

## 0:15 — 0:45 · Patient intake — text + image

Open `http://localhost:3000` → Patient Portal → Get Diagnosis.
Type age `8`, sex `Female`. Click **Start**.

Type: *"My daughter keeps scratching her elbow at night. The skin gets red and flaky."*

Click **attach image**, pick a photo of atopic dermatitis. Click **Send**.

Show Gemma 4 reply describing the lesion morphology and asking one targeted
follow-up. Expand the **tool calls** disclosure — viewer sees `lookup_disease`
and the structured KB response.

## 0:45 — 1:15 · Voice intake (accessibility angle)

Click **record voice**, speak: *"She has had this for three weeks. We tried
calamine lotion. There's no fever."* Stop recording → Send.

Show Gemma 4 incorporating the voice content. Final assistant message:
`submit_diagnosis_report` fires → urgency banner: **GREEN**, top diagnosis
**Atopic Dermatitis**, recommended specialty **Dermatology**, follow-up in 7
days.

## 1:15 — 1:45 · Red-flag emergency

Reload the page. New patient: age `58`, sex `Male`.

Type: *"Crushing chest pain spreading to my left arm, sweating heavily."*

Within one round-trip Gemma 4 calls `triage_severity` → `urgency=red`, then
`submit_diagnosis_report` → red banner appears with "**Seek emergency care
now**".

Narrator: "The model didn't decide this was an emergency on vibes. It called a
deterministic triage tool that lives on this laptop, with rules a human
clinician can audit. That's what makes function calling a safety feature."

## 1:45 — 2:15 · Doctor side

Open Doctors Portal. Click **Generate Diagnosis** on the first listed case.
Click **Draft with Gemma 4**.

Show the SOAP-style note appearing. Expand **tool calls** — viewer sees
`check_drug_interactions` was called with the patient's medications and surfaced
a **major** interaction (e.g. aspirin + warfarin).

Narrator: "The doctor accepts or edits the draft — Gemma 4 never writes the
final prescription."

## 2:15 — 2:45 · The pitch

> Cut back to the laptop, airplane mode badge in the corner.
> Narrator: "AyuConnect is built for the clinic that has a laptop but no
> reliable internet, and for the patient whose data should never leave their
> country. Gemma 4 is the first open model that makes this stack possible on
> commodity hardware. Code, notebook, and writeup at github.com/VineethRV/AyuConnect."

End card: AyuConnect logo · Gemma 4 Good Hackathon · Health & Sciences track.

---

## Shot checklist for the day

- [ ] Airplane mode badge visible at least twice.
- [ ] One shot of `ollama list` confirming the local model.
- [ ] One shot of `/health` endpoint output.
- [ ] At least one **tool calls** disclosure opened on camera.
- [ ] Both green and red urgency banners shown.
- [ ] Voice recording UI in the act of recording (red pulse).
- [ ] Doctor-side draft + drug-interaction warning expansion.

## Recording tips

* Use OBS with a 1080p screen capture; mic at 48kHz.
* Pre-pull `gemma4:e4b` and warm the model with one throw-away request so the
  first on-camera response doesn't pay the cold-start latency.
* Keep the patient names obviously fictional ("Dev Patel demo case").
