"use client";

import Loading from "@/app/components/Loading";
import { draftConsultationNote, type ChatTurn, type ToolInvocation } from "@/app/lib/api";
import React, { useEffect, useState } from "react";
import { toast } from "sonner";

interface PatientInfo {
  patient_name: string;
  patient_sex: string;
  patient_age: number;
  disease_predicted_1: string;
  disease_predicted_2: string;
  disease_predicted_3: string;
  symptom_list: string[];
  conversation_list: string[];
  medicines: string;
}

const MOCK: PatientInfo = {
  patient_name: "John Doe",
  patient_sex: "Male",
  patient_age: 45,
  disease_predicted_1: "Diabetes",
  disease_predicted_2: "Hypertension",
  disease_predicted_3: "Asthma",
  symptom_list: ["Fatigue", "Shortness of breath", "Increased thirst"],
  conversation_list: [
    "Discussed high blood sugar levels on 2023-01-15",
    "Follow-up on medication adherence on 2023-02-10",
    "Reported symptoms of breathlessness on 2023-03-20",
  ],
  medicines: "Metformin, Amlodipine, Salbutamol Inhaler",
};

export default function GenerateDiagnosisPage() {
  const [patient, setPatient] = useState<PatientInfo>(MOCK);
  const [doctorQuestion, setDoctorQuestion] = useState(
    "Please draft a SOAP-style consultation note and flag any drug interactions."
  );
  const [note, setNote] = useState("");
  const [tools, setTools] = useState<ToolInvocation[]>([]);
  const [loading, setLoading] = useState(false);
  const [list, setList] = useState<string[]>([]);
  const [medicines, setMedicines] = useState("");

  useEffect(() => {
    try {
      const raw = localStorage.getItem("patient");
      if (raw) setPatient(JSON.parse(raw));
    } catch {
      /* fall back to mock */
    }
  }, []);

  const generate = async () => {
    setLoading(true);
    setNote("");
    setTools([]);
    const transcript: ChatTurn[] = [
      {
        role: "user",
        content: `Patient ${patient.patient_name}, ${patient.patient_age}y ${patient.patient_sex}. Top intake-suggested conditions: ${patient.disease_predicted_1}, ${patient.disease_predicted_2}, ${patient.disease_predicted_3}.`,
      },
      {
        role: "user",
        content: `Symptoms: ${patient.symptom_list.join(", ")}`,
      },
      {
        role: "user",
        content: `Current medications: ${patient.medicines || "none"}`,
      },
      ...patient.conversation_list.map((c) => ({ role: "user" as const, content: c })),
    ];
    try {
      const resp = await draftConsultationNote({
        transcript,
        doctor_question: doctorQuestion,
      });
      setNote(resp.note);
      setTools(resp.tool_calls);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not reach backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="py-8 min-h-screen"
      style={{
        backgroundImage: 'url("/bg-patient.png")',
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      <div className="bg-gray-50 p-6 rounded-lg shadow-md max-w-4xl mx-auto">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gray-800">Patient Information</h1>
          <p className="text-gray-600">
            Doctor-side review — Gemma 4 drafts, you decide.
          </p>
        </div>

        <div className="bg-white p-4 rounded-md shadow-sm mb-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">Basic Information</h2>
          <div className="grid grid-cols-3 gap-4 text-gray-600">
            <p><span className="font-medium">Name:</span> {patient.patient_name}</p>
            <p><span className="font-medium">Sex:</span> {patient.patient_sex}</p>
            <p><span className="font-medium">Age:</span> {patient.patient_age}</p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-md shadow-sm mb-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">Predicted Diseases (from intake)</h2>
          <ul className="list-disc list-inside text-gray-600">
            <li>{patient.disease_predicted_1}</li>
            <li>{patient.disease_predicted_2}</li>
            <li>{patient.disease_predicted_3}</li>
          </ul>
        </div>

        <div className="bg-white p-4 rounded-md shadow-sm mb-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">Symptoms</h2>
          <ul className="list-disc list-inside text-gray-600">
            {patient.symptom_list.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>

        <div className="bg-white p-4 rounded-md shadow-sm mb-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">Conversation history</h2>
          <ul className="space-y-2 text-gray-600">
            {patient.conversation_list.map((c, i) => (
              <li key={i} className="p-2 bg-gray-100 rounded-md shadow-sm">{c}</li>
            ))}
          </ul>
        </div>

        <div className="flex space-x-2 justify-center py-4">
          <input
            type="text"
            placeholder="Add a medicine"
            className="border border-gray-300 p-2 rounded-md w-1/2"
            value={medicines}
            onChange={(e) => setMedicines(e.target.value)}
          />
          <button
            onClick={() => {
              if (!medicines.trim()) return;
              setList((prev) => [...prev, medicines.trim()]);
              setMedicines("");
            }}
            className="bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600"
          >
            Add
          </button>
        </div>

        <div className="bg-white p-4 rounded-md shadow-sm mb-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">Prescription</h2>
          <p className="text-gray-600">{list.join(", ") || "(none)"}</p>
        </div>

        <div className="bg-white p-4 rounded-md shadow-sm mb-4">
          <h2 className="text-lg font-semibold text-gray-700 mb-2">Ask the assistant</h2>
          <textarea
            value={doctorQuestion}
            onChange={(e) => setDoctorQuestion(e.target.value)}
            className="border p-2 border-gray-300 h-[80px] rounded-md w-full text-gray-700"
          />
          <div className="flex justify-center mt-3">
            <button
              onClick={generate}
              disabled={loading}
              className="bg-green-600 text-white px-5 py-2 rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              {loading ? "Drafting…" : "Draft with Gemma 4"}
            </button>
          </div>
        </div>

        {loading && <Loading />}

        {note && (
          <div className="bg-white p-4 rounded-md shadow-sm mb-4">
            <h2 className="text-lg font-semibold text-gray-700 mb-2">Drafted note</h2>
            <pre className="whitespace-pre-wrap text-gray-700 text-sm font-sans">{note}</pre>
            {tools.length > 0 && (
              <details className="mt-3 text-xs text-gray-500">
                <summary className="cursor-pointer">Tool calls Gemma made ({tools.length})</summary>
                <ul className="mt-2 space-y-2 font-mono">
                  {tools.map((t, i) => (
                    <li key={i}>
                      <span className="font-semibold">{t.name}</span>
                      <pre className="bg-gray-100 p-2 rounded text-[11px] overflow-x-auto">
{JSON.stringify({ args: t.arguments, result: t.result }, null, 2)}
                      </pre>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
