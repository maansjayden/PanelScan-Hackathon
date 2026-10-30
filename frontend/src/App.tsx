import { useRef, useState } from "react";

const API = "http://localhost:8000";

type DamageItem = {
  panel_name: string;
  damage_type: string;
  recommended_action: "repair" | "replace";
  ai_confidence_score: number;
};
type QuoteEstimate = {
  vehicle_summary: string;
  damage_items: DamageItem[];
  total_parts_estimate_zar: number;
  total_labor_hours: number;
};

export default function App() {
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<QuoteEstimate | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  function pickImage(f: File | undefined) {
    if (!f) return;
    setImage(f);
    setPreview(URL.createObjectURL(f));
  }

  async function toggleRecord() {
    if (recording) {
      recRef.current?.stop();
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    chunksRef.current = [];
    rec.ondataavailable = (e) => chunksRef.current.push(e.data);
    rec.onstop = () => {
      setAudioBlob(new Blob(chunksRef.current, { type: rec.mimeType }));
      stream.getTracks().forEach((t) => t.stop());
      setRecording(false);
    };
    recRef.current = rec;
    rec.start();
    setRecording(true);
  }

  async function submit() {
    if (!image || !audioBlob) {
      setError("Add a damage photo and a voice memo first.");
      return;
    }
    setBusy(true);
    setError(null);
    setQuote(null);
    try {
      const fd = new FormData();
      fd.append("image", image);
      fd.append("audio", audioBlob, "memo.webm");
      const res = await fetch(`${API}/api/assess-damage`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error(`Backend ${res.status}: ${await res.text()}`);
      setQuote(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-sm font-semibold text-amber-400">PanelScan</p>
        <h1 className="mt-1 text-3xl font-bold">Workshop damage assessment</h1>
        <p className="mt-2 text-neutral-300">
          Photograph the damage, speak your assessment, get an itemized quote.
        </p>

        <div className="mt-8 grid gap-6 md:grid-cols-2">
          <label className="block cursor-pointer rounded-lg border border-neutral-700 bg-neutral-900 p-4">
            <span className="text-sm font-semibold">1. Damage photo</span>
            <input
              type="file"
              accept="image/*"
              className="mt-2 block w-full text-sm"
              onChange={(e) => pickImage(e.target.files?.[0])}
            />
            {preview && (
              <img src={preview} alt="damage preview" className="mt-3 rounded-md" />
            )}
          </label>

          <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
            <span className="text-sm font-semibold">2. Voice memo</span>
            <div className="mt-2 flex items-center gap-3">
              <button
                onClick={toggleRecord}
                className={`rounded-md px-4 py-2 text-sm font-bold ${
                  recording ? "bg-red-600" : "bg-amber-500 text-black"
                }`}
              >
                {recording ? "Stop" : "Record"}
              </button>
              <span className="text-sm text-neutral-300">
                {recording
                  ? "Listening…"
                  : audioBlob
                    ? "Memo captured"
                    : "No memo yet"}
              </span>
            </div>
            <input
              type="file"
              accept="audio/*"
              className="mt-3 block w-full text-sm"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) setAudioBlob(f);
              }}
            />
          </div>
        </div>

        <button
          onClick={submit}
          disabled={busy}
          className="mt-6 w-full rounded-md bg-amber-500 py-3 font-bold text-black disabled:opacity-50"
        >
          {busy ? "Assessing…" : "Generate quote"}
        </button>
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

        {quote && (
          <div className="mt-8 rounded-lg border border-neutral-700 bg-neutral-900 p-5">
            <h2 className="text-xl font-bold">{quote.vehicle_summary}</h2>
            <ul className="mt-4 divide-y divide-neutral-800">
              {quote.damage_items.map((d) => (
                <li key={d.panel_name} className="py-3">
                  <div className="flex justify-between gap-4">
                    <div>
                      <p className="font-semibold capitalize">{d.panel_name}</p>
                      <p className="text-sm text-neutral-300">
                        {d.damage_type} · {d.recommended_action}
                      </p>
                    </div>
                    <span className="text-sm text-amber-400">
                      {Math.round(d.ai_confidence_score * 100)}%
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 rounded bg-neutral-800">
                    <div
                      className="h-1.5 rounded bg-amber-500"
                      style={{ width: `${d.ai_confidence_score * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex justify-between border-t border-neutral-700 pt-4 font-bold">
              <span>Parts R{quote.total_parts_estimate_zar.toFixed(2)}</span>
              <span>{quote.total_labor_hours} labour hrs</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
