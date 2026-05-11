// Thin client for the AyuConnect Gemma 4 backend.
// All Gemma 4 inference happens server-side; the browser never talks to a
// cloud LLM directly. That means we can deploy the backend on the same LAN as
// the clinic and keep patient data entirely on-prem.

export type Role = "system" | "user" | "assistant" | "tool";

export interface ChatTurn {
  role: Role;
  content: string;
}

export interface ToolInvocation {
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
}

export interface DiagnosisSummary {
  top_diseases: string[];
  symptoms: string[];
  urgency: "red" | "yellow" | "green";
  urgency_reason: string;
  recommended_specialty: string;
  follow_up_in_days: number;
  drug_interactions: string[];
  notes: string;
}

export interface ChatResponse {
  assistant_message: string;
  tool_calls: ToolInvocation[];
  final: boolean;
  summary: DiagnosisSummary | null;
}

export interface ChatRequest {
  history: ChatTurn[];
  user_message: string;
  image_b64?: string | null;
  image_mime?: string | null;
  audio_b64?: string | null;
  audio_mime?: string | null;
  patient_age?: number | null;
  patient_sex?: string | null;
}

const BASE_URL =
  process.env.NEXT_PUBLIC_AYU_API_URL ?? "http://localhost:8000";

export async function chat(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Backend ${res.status}: ${text}`);
  }
  return (await res.json()) as ChatResponse;
}

export interface ReportRequest {
  transcript: ChatTurn[];
  doctor_question: string;
}

export interface ReportResponse {
  note: string;
  tool_calls: ToolInvocation[];
}

export async function draftConsultationNote(
  req: ReportRequest
): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Backend ${res.status}: ${await res.text()}`);
  return (await res.json()) as ReportResponse;
}

export async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  // Browser-side: avoid String.fromCharCode for very large files.
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(
      null,
      Array.from(bytes.subarray(i, i + chunk))
    );
  }
  return btoa(binary);
}
