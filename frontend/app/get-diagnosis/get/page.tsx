"use client";

import Loading from "@/app/components/Loading";
import {
  chat,
  fileToBase64,
  type ChatTurn,
  type DiagnosisSummary,
  type ToolInvocation,
} from "@/app/lib/api";
import React, { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

type Bubble = ChatTurn & { tools?: ToolInvocation[] };

const URGENCY_STYLE: Record<DiagnosisSummary["urgency"], string> = {
  red: "bg-red-100 border-red-400 text-red-900",
  yellow: "bg-yellow-100 border-yellow-400 text-yellow-900",
  green: "bg-green-100 border-green-400 text-green-900",
};

export default function PatientIntakePage() {
  const [transcript, setTranscript] = useState<Bubble[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<DiagnosisSummary | null>(null);
  const [pendingImage, setPendingImage] = useState<File | null>(null);
  const [pendingAudio, setPendingAudio] = useState<Blob | null>(null);
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const [meta, setMeta] = useState({ age: "", sex: "" });
  const [metaLocked, setMetaLocked] = useState(false);

  useEffect(() => {
    // Greet the user with a fixed opener so they know what to do without a
    // round-trip to the model — saves latency and works fully offline-cold.
    setTranscript([
      {
        role: "assistant",
        content:
          "Hi, I'm Ayu. I'll ask a few questions to prepare your case for the doctor. You can also send a photo of the affected area or record a voice note. Let's start — what's bothering you today?",
      },
    ]);
  }, []);

  const send = async () => {
    if (loading || (!draft.trim() && !pendingImage && !pendingAudio)) return;

    let image_b64: string | null = null;
    let image_mime: string | null = null;
    let audio_b64: string | null = null;
    let audio_mime: string | null = null;

    if (pendingImage) {
      image_b64 = await fileToBase64(pendingImage);
      image_mime = pendingImage.type || "image/png";
    }
    if (pendingAudio) {
      const file = new File([pendingAudio], "note.webm", {
        type: pendingAudio.type || "audio/webm",
      });
      audio_b64 = await fileToBase64(file);
      audio_mime = file.type;
    }

    const userBubble: Bubble = {
      role: "user",
      content: draft || (pendingImage ? "[image attached]" : pendingAudio ? "[voice note]" : ""),
    };
    const history: ChatTurn[] = transcript.map(({ role, content }) => ({ role, content }));
    const nextTranscript = [...transcript, userBubble];
    setTranscript(nextTranscript);
    setDraft("");
    setPendingImage(null);
    setPendingAudio(null);
    setLoading(true);

    try {
      const resp = await chat({
        history,
        user_message: userBubble.content,
        image_b64,
        image_mime,
        audio_b64,
        audio_mime,
        patient_age: meta.age ? Number(meta.age) : null,
        patient_sex: meta.sex || null,
      });

      setTranscript([
        ...nextTranscript,
        {
          role: "assistant",
          content: resp.assistant_message,
          tools: resp.tool_calls,
        },
      ]);
      if (resp.final && resp.summary) {
        setSummary(resp.summary);
        if (resp.summary.urgency === "red") {
          toast.error("Emergency: seek immediate medical care.");
        }
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to contact backend.");
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: rec.mimeType || "audio/webm",
        });
        setPendingAudio(blob);
        stream.getTracks().forEach((t) => t.stop());
      };
      rec.start();
      recorderRef.current = rec;
      setRecording(true);
    } catch {
      toast.error("Microphone permission denied.");
    }
  };

  const stopRecording = () => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  };

  const submitMeta = () => {
    if (!meta.age || !meta.sex) {
      toast.error("Enter age and sex first.");
      return;
    }
    setMetaLocked(true);
  };

  return (
    <div
      className="min-h-screen w-full bg-gray-100 flex flex-col items-center px-4 py-6"
      style={{
        backgroundImage: 'url("/bg-patient.png")',
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      <div className="w-full max-w-3xl bg-white shadow-xl rounded-2xl flex flex-col overflow-hidden">
        <header className="px-6 py-4 border-b bg-white">
          <h1 className="text-2xl font-semibold text-gray-800">Ayu — Patient Intake</h1>
          <p className="text-sm text-gray-500">
            Powered locally by Gemma 4 · your data never leaves this device
          </p>
        </header>

        {!metaLocked && (
          <div className="px-6 py-4 flex gap-3 items-end bg-gray-50 border-b">
            <label className="flex flex-col text-sm text-gray-700">
              Age
              <input
                type="number"
                value={meta.age}
                onChange={(e) => setMeta({ ...meta, age: e.target.value })}
                className="border border-gray-300 rounded px-2 py-1 w-24"
              />
            </label>
            <label className="flex flex-col text-sm text-gray-700">
              Sex
              <select
                value={meta.sex}
                onChange={(e) => setMeta({ ...meta, sex: e.target.value })}
                className="border border-gray-300 rounded px-2 py-1"
              >
                <option value="">—</option>
                <option value="Female">Female</option>
                <option value="Male">Male</option>
                <option value="Other">Other</option>
              </select>
            </label>
            <button
              onClick={submitMeta}
              className="ml-auto px-4 py-2 bg-[#ff787f] text-white rounded hover:bg-[#ff999e]"
            >
              Start
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 min-h-[400px] max-h-[60vh] bg-white">
          {transcript.map((b, i) => (
            <div key={i} className={b.role === "user" ? "flex justify-end" : ""}>
              <div
                className={[
                  "max-w-[80%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap",
                  b.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-800",
                ].join(" ")}
              >
                <div>{b.content}</div>
                {b.tools && b.tools.length > 0 && (
                  <details className="mt-2 text-xs opacity-80">
                    <summary className="cursor-pointer">
                      tool calls ({b.tools.length})
                    </summary>
                    <ul className="mt-1 space-y-1">
                      {b.tools.map((t, j) => (
                        <li key={j} className="font-mono">
                          <span className="font-semibold">{t.name}</span>(
                          {Object.entries(t.arguments)
                            .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                            .join(", ")}
                          )
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            </div>
          ))}
          {loading && <Loading />}
        </div>

        {summary ? (
          <section className={`border-t-4 px-6 py-4 ${URGENCY_STYLE[summary.urgency]}`}>
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-semibold text-lg">
                Intake complete — urgency: <span className="uppercase">{summary.urgency}</span>
              </h2>
              <span className="text-xs">
                Follow up within {summary.follow_up_in_days} day(s) · {summary.recommended_specialty}
              </span>
            </div>
            <p className="text-sm italic mb-2">{summary.urgency_reason}</p>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="font-semibold mb-1">Top candidate conditions</div>
                <ul className="list-disc list-inside">
                  {summary.top_diseases.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="font-semibold mb-1">Symptoms recorded</div>
                <ul className="list-disc list-inside">
                  {summary.symptoms.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            </div>
            {summary.drug_interactions.length > 0 && (
              <div className="mt-2 text-sm">
                <span className="font-semibold">Drug interactions: </span>
                {summary.drug_interactions.join("; ")}
              </div>
            )}
            {summary.notes && (
              <div className="mt-2 text-sm">
                <span className="font-semibold">Notes: </span>
                {summary.notes}
              </div>
            )}
            <button
              onClick={() => {
                localStorage.setItem(
                  "ayu_last_summary",
                  JSON.stringify({ summary, transcript })
                );
                toast.success("Report saved locally — show this to your doctor.");
              }}
              className="mt-3 px-3 py-1.5 bg-white border border-current rounded text-sm"
            >
              Save report
            </button>
          </section>
        ) : (
          metaLocked && (
            <footer className="border-t bg-gray-50 px-6 py-3 space-y-2">
              <div className="flex gap-2 items-center text-xs text-gray-600">
                <label className="cursor-pointer underline">
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) =>
                      e.target.files?.[0] && setPendingImage(e.target.files[0])
                    }
                  />
                  attach image
                </label>
                {pendingImage && (
                  <span>· {pendingImage.name} <button onClick={() => setPendingImage(null)} className="text-red-500">×</button></span>
                )}
                {!recording ? (
                  <button onClick={startRecording} className="underline">
                    record voice
                  </button>
                ) : (
                  <button onClick={stopRecording} className="underline text-red-600 animate-pulse">
                    stop recording
                  </button>
                )}
                {pendingAudio && !recording && (
                  <span>· voice note ready <button onClick={() => setPendingAudio(null)} className="text-red-500">×</button></span>
                )}
              </div>
              <div className="flex gap-2">
                <textarea
                  rows={2}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  placeholder="Describe what you're feeling…"
                  className="flex-1 border border-gray-300 rounded p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
                <button
                  onClick={send}
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  Send
                </button>
              </div>
            </footer>
          )
        )}
      </div>
    </div>
  );
}
