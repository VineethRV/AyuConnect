"use client"

import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  return (
  <div style={{
    backgroundImage: 'url("/dash.png")',
    backgroundSize: "cover",
    backgroundPosition: "center",
  }} 
   className="h-screen bg-gray-100 min-h-screen flex flex-col items-center">
    <header className="header text-black bg-white w-full py-4 flex flex-col items-center">
      <h1 className="text-3xl font-bold">Welcome to AyuConnect</h1>
      <p className="text-base mt-2">
        On-device medical intake, powered by <span className="font-semibold">Gemma 4</span>. Privacy-first. Works offline.
      </p>
    </header>
    <section className="features justify-center items-center flex flex-col space-x-8 md:flex-row h-full w-full">
      <div className="feature bg-white shadow-md rounded-lg p-6 w-80 text-center">
        <h2 className="text-2xl font-semibold mb-2">Patient Portal</h2>
        <p className="text-gray-700">
          Talk, type, or send a photo — Gemma 4 prepares your case for the doctor with full transparency over every tool it uses.
        </p>
        <button onClick={()=>router.push('/get-diagnosis')} className="mt-4 bg-[#ff787f] text-white py-2 px-4 rounded hover:bg-[#ff999e] transition duration-300">Get Diagnosis</button>
      </div>
      <div className="feature bg-white shadow-md rounded-lg p-6 w-80 text-center">
        <h2 className="text-2xl font-semibold mb-2">Doctors Portal</h2>
        <p className="text-gray-700">
          Review AI-prepared intakes, draft consultation notes, and check drug interactions — all offline on your laptop.
        </p>
        <button onClick={()=>router.push('/give-diagnosis')} className="mt-4 bg-[#ff787f] text-white py-2 px-4 rounded hover:bg-[#ff999e] transition duration-300">Give diagnosis</button>
      </div>
    </section>
    <footer className="text-black bg-white w-full py-4 flex justify-center">
      <p>&copy; 2026 AyuConnect · Apache 2.0 · Built on Gemma 4</p>
    </footer>
  </div>
  );
}
