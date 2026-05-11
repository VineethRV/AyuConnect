# AyuConnect frontend

Next.js 14 client for the AyuConnect Gemma 4 backend.

## Run locally

```bash
cp .env.example .env.local        # then point NEXT_PUBLIC_AYU_API_URL at your backend
npm install
npm run dev
```

The frontend never talks to a cloud LLM directly — every Gemma 4 call goes
through the FastAPI backend, which in turn talks to Ollama, vLLM, or a
Transformers in-process runtime. That keeps patient data on the device the
clinic controls.

## Notable files

- `app/lib/api.ts` — typed client for `/chat`, `/report`, `/triage`.
- `app/get-diagnosis/get/page.tsx` — patient intake UI with image upload, voice
  recording, and a tool-call transparency panel.
- `app/give-diagnosis/generate/page.tsx` — doctor-side consultation note draft.

## Tests

Type-check with `npm run build` (or `npx tsc --noEmit`).
