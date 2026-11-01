import { useEffect, useRef, useState, type DragEvent } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

type CustomerEstimate = QuoteEstimate & {
  labour_rate_zar: number;
  labour_estimate_zar: number;
  total_estimate_zar: number;
  status: "pending" | "approved" | "changes_requested";
  created_at: string;
  decision_at: string | null;
};

const WAV_SAMPLE_RATE = 24000;

async function toWav(source: Blob): Promise<Blob> {
  const context = new AudioContext();
  let decoded: AudioBuffer;
  try {
    decoded = await context.decodeAudioData(await source.arrayBuffer());
  } finally {
    await context.close();
  }

  const sampleCount = Math.ceil(decoded.duration * WAV_SAMPLE_RATE);
  if (sampleCount < 1 || decoded.numberOfChannels < 1) {
    throw new Error("The audio recording is empty or could not be decoded.");
  }

  const dataSize = sampleCount * 2;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);
  const writeText = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, WAV_SAMPLE_RATE, true);
  view.setUint32(28, WAV_SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, dataSize, true);

  const channels = Array.from(
    { length: decoded.numberOfChannels },
    (_, channel) => decoded.getChannelData(channel),
  );
  for (let i = 0; i < sampleCount; i += 1) {
    const position = (i * decoded.sampleRate) / WAV_SAMPLE_RATE;
    const first = Math.min(Math.floor(position), decoded.length - 1);
    const second = Math.min(first + 1, decoded.length - 1);
    const fraction = position - first;
    const mixed =
      channels.reduce((sum, channel) => {
        const sample =
          channel[first] + (channel[second] - channel[first]) * fraction;
        return sum + sample;
      }, 0) / channels.length;
    const clipped = Math.max(-1, Math.min(1, mixed));
    view.setInt16(
      44 + i * 2,
      clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff,
      true,
    );
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function Icon({
  name,
  size = 20,
}: {
  name: "route" | "camera" | "microphone" | "upload" | "check" | "refresh" | "alert";
  size?: number;
}) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {name === "route" && (
        <>
          <circle cx="5" cy="18" r="2" />
          <circle cx="19" cy="6" r="2" />
          <path d="M7 18h3a3 3 0 0 0 3-3v-6a3 3 0 0 1 3-3h1" />
        </>
      )}
      {name === "camera" && (
        <>
          <path d="M4 8.5h3l1.5-2h7l1.5 2h3A1.5 1.5 0 0 1 21.5 10v8A1.5 1.5 0 0 1 20 19.5H4A1.5 1.5 0 0 1 2.5 18v-8A1.5 1.5 0 0 1 4 8.5Z" />
          <circle cx="12" cy="13.5" r="3.25" />
        </>
      )}
      {name === "microphone" && (
        <>
          <rect x="9" y="3" width="6" height="12" rx="3" />
          <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3m-4 0h8" />
        </>
      )}
      {name === "upload" && (
        <>
          <path d="M12 16V4m-4 4 4-4 4 4" />
          <path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" />
        </>
      )}
      {name === "check" && <path d="m5 12.5 4.5 4.5L19 7" />}
      {name === "refresh" && (
        <>
          <path d="M20 7v5h-5" />
          <path d="M4.6 9a8 8 0 0 1 13.2-2L20 12M4 17v-5h5" />
          <path d="M19.4 15a8 8 0 0 1-13.2 2L4 12" />
        </>
      )}
      {name === "alert" && (
        <>
          <path d="M12 3 2.8 19a1.2 1.2 0 0 0 1 1.8h16.4a1.2 1.2 0 0 0 1-1.8L12 3Z" />
          <path d="M12 9v4m0 3h.01" />
        </>
      )}
    </svg>
  );
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
  }).format(value);
}

function formatDuration(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
}

export default function App() {
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioPreview, setAudioPreview] = useState<string | null>(null);
  const [audioName, setAudioName] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [recordingStartedAt, setRecordingStartedAt] = useState<number | null>(
    null,
  );
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [busy, setBusy] = useState(false);
  const [draggingPhoto, setDraggingPhoto] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<QuoteEstimate | null>(null);
  const [reviewedItems, setReviewedItems] = useState<number[]>([]);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [labourRate, setLabourRate] = useState("");
  const [approvalToken, setApprovalToken] = useState<string | null>(null);
  const [approvalStatus, setApprovalStatus] = useState<CustomerEstimate | null>(
    null,
  );
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const previewUrlRef = useRef<string | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const photoInputRef = useRef<HTMLInputElement | null>(null);
  const audioInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (recordingStartedAt === null) return;
    const updateDuration = () => {
      setRecordingSeconds(Math.floor((Date.now() - recordingStartedAt) / 1000));
    };
    const intervalId = window.setInterval(updateDuration, 1000);
    return () => window.clearInterval(intervalId);
  }, [recordingStartedAt]);

  useEffect(
    () => () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
      const recorder = recRef.current;
      if (recorder?.state === "recording") {
        recorder.onstop = null;
        recorder.onerror = null;
        recorder.stop();
      }
    },
    [],
  );

  function clearPhoto() {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
    setPreview(null);
    setImage(null);
  }

  function clearAudio() {
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = null;
    setAudioPreview(null);
    setAudioBlob(null);
    setAudioName(null);
  }

  function storeAudio(blob: Blob, name: string) {
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    const objectUrl = URL.createObjectURL(blob);
    audioUrlRef.current = objectUrl;
    setAudioBlob(blob);
    setAudioPreview(objectUrl);
    setAudioName(name);
  }

  function pickImage(file: File | undefined) {
    if (!file || busy) return;
    if (!file.type.startsWith("image/")) {
      setError("Choose an image file for the damage photo.");
      return;
    }
    setError(null);
    setQuote(null);
    setReviewedItems([]);
    setCopyStatus(null);
    setApprovalToken(null);
    setApprovalStatus(null);
    setApprovalError(null);
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    const objectUrl = URL.createObjectURL(file);
    previewUrlRef.current = objectUrl;
    setPreview(objectUrl);
    setImage(file);
  }

  function pickAudio(file: File | undefined) {
    if (!file || busy) return;
    if (!file.type.startsWith("audio/")) {
      setError("Choose an audio file for the voice note.");
      return;
    }
    setError(null);
    setQuote(null);
    setReviewedItems([]);
    setCopyStatus(null);
    setApprovalToken(null);
    setApprovalStatus(null);
    setApprovalError(null);
    storeAudio(file, file.name);
    setRecordingSeconds(0);
  }

  function handlePhotoDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDraggingPhoto(false);
    if (busy) return;
    pickImage(event.dataTransfer.files[0]);
  }

  async function toggleRecord() {
    if (recording) {
      recRef.current?.stop();
      return;
    }

    setError(null);
    setQuote(null);
    setReviewedItems([]);
    setCopyStatus(null);
    setApprovalToken(null);
    setApprovalStatus(null);
    setApprovalError(null);
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
        throw new Error(
          "Audio recording is unavailable in this browser. Upload a voice memo instead.",
        );
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      clearAudio();
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        setError("The recording stopped unexpectedly. Try again or upload a memo.");
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setRecording(false);
        setRecordingStartedAt(null);
      };
      recorder.onstop = () => {
        const recordingBlob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        if (recordingBlob.size > 0) {
          storeAudio(recordingBlob, "Recorded voice memo");
        } else {
          setError("No audio was captured. Try again or upload a voice memo.");
        }
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setRecording(false);
        setRecordingStartedAt(null);
      };
      recRef.current = recorder;
      recorder.start();
      setRecordingSeconds(0);
      setRecordingStartedAt(Date.now());
      setRecording(true);
    } catch (caught) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setError(
        caught instanceof Error
          ? caught.message
          : "Microphone access could not be started.",
      );
    }
  }

  function startNewAssessment() {
    if (recRef.current?.state === "recording") {
      recRef.current.onstop = null;
      recRef.current.onerror = null;
      recRef.current.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    clearPhoto();
    clearAudio();
    setRecording(false);
    setRecordingStartedAt(null);
    setRecordingSeconds(0);
    setError(null);
    setQuote(null);
    setReviewedItems([]);
    setCopyStatus(null);
    setLabourRate("");
    setApprovalToken(null);
    setApprovalStatus(null);
    setApprovalError(null);
    if (photoInputRef.current) photoInputRef.current.value = "";
    if (audioInputRef.current) audioInputRef.current.value = "";
  }

  async function submit() {
    if (!image || !audioBlob) {
      setError("Add a damage photo and a voice memo before generating an estimate.");
      return;
    }
    setBusy(true);
    setError(null);
    setQuote(null);
    try {
      const formData = new FormData();
      formData.append("image", image);
      formData.append("audio", await toWav(audioBlob), "memo.wav");
      const response = await fetch(`${API}/api/assess-damage`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(
          `The assessment could not be completed (${response.status}): ${await response.text()}`,
        );
      }
      const estimate = (await response.json()) as QuoteEstimate;
      setReviewedItems([]);
      setCopyStatus(null);
      setLabourRate("");
      setApprovalToken(null);
      setApprovalStatus(null);
      setApprovalError(null);
      setQuote(estimate);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The upload failed.");
    } finally {
      setBusy(false);
    }
  }

  function toggleReviewed(index: number) {
    setReviewedItems((current) =>
      current.includes(index)
        ? current.filter((item) => item !== index)
        : [...current, index],
    );
  }

  async function createApprovalLink() {
    if (!quote || reviewedCount !== quote.damage_items.length) return;
    const rate = Number(labourRate);
    if (!Number.isFinite(rate) || rate <= 0) {
      setApprovalError("Enter a workshop labour rate greater than zero.");
      return;
    }

    setApprovalBusy(true);
    setApprovalError(null);
    try {
      const response = await fetch(`${API}/api/approvals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estimate: quote, labour_rate_zar: rate }),
      });
      if (!response.ok) {
        throw new Error(
          `The approval link could not be created (${response.status}).`,
        );
      }
      const result = (await response.json()) as { approval_token: string };
      setApprovalToken(result.approval_token);
      const statusResponse = await fetch(
        `${API}/api/approvals/${encodeURIComponent(result.approval_token)}`,
      );
      if (!statusResponse.ok) {
        throw new Error(
          `The estimate was saved, but its status could not be loaded (${statusResponse.status}).`,
        );
      }
      setApprovalStatus((await statusResponse.json()) as CustomerEstimate);
    } catch (caught) {
      setApprovalError(
        caught instanceof Error
          ? caught.message
          : "The approval link could not be created.",
      );
    } finally {
      setApprovalBusy(false);
    }
  }

  async function refreshApprovalStatus() {
    if (!approvalToken) return;
    setApprovalBusy(true);
    setApprovalError(null);
    try {
      const response = await fetch(
        `${API}/api/approvals/${encodeURIComponent(approvalToken)}`,
      );
      if (!response.ok) {
        throw new Error(
          `Approval status could not be loaded (${response.status}).`,
        );
      }
      setApprovalStatus((await response.json()) as CustomerEstimate);
    } catch (caught) {
      setApprovalError(
        caught instanceof Error
          ? caught.message
          : "Approval status could not be loaded.",
      );
    } finally {
      setApprovalBusy(false);
    }
  }

  async function copyApprovalLink() {
    if (!approvalToken || !navigator.clipboard?.writeText) {
      setApprovalError("Clipboard access is unavailable. Copy the link from the field.");
      return;
    }
    const link = new URL(
      `/approval/${encodeURIComponent(approvalToken)}`,
      window.location.origin,
    ).toString();
    try {
      await navigator.clipboard.writeText(link);
      setCopyStatus("Customer approval link copied.");
      setApprovalError(null);
    } catch {
      setApprovalError("Clipboard access was denied. Copy the link from the field.");
    }
  }

  async function copyDraft() {
    if (!quote) return;
    if (!navigator.clipboard?.writeText) {
      setError("Clipboard access is unavailable. Select and copy the draft manually.");
      return;
    }

    const lines = [
      "PanelScan repair estimate - subject to workshop approval",
      "Workshop approval is required before sharing with a customer.",
      "",
      `Vehicle: ${quote.vehicle_summary}`,
      "",
      ...quote.damage_items.map((damage, index) => {
        const reviewLabel = reviewedItems.includes(index) ? "checked" : "not checked";
        return `${index + 1}. ${damage.panel_name}: ${damage.damage_type}; ${damage.recommended_action}; ${Math.round(damage.ai_confidence_score * 100)}% model confidence indicator; ${reviewLabel}`;
      }),
      "",
      `Estimated parts: ${formatCurrency(quote.total_parts_estimate_zar)}`,
      `Estimated labour: ${quote.total_labor_hours} hours`,
      "Parts prices are estimates, not supplier-verified quotes.",
    ];

    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopyStatus("Draft copied to clipboard.");
      setError(null);
    } catch {
      setError("Clipboard access was denied. Select and copy the draft manually.");
    }
  }

  const photoComplete = image !== null;
  const audioComplete = audioBlob !== null;
  const estimateReady = photoComplete && audioComplete && !recording && !busy;
  const parsedLabourRate = Number(labourRate);
  const labourRateIsValid =
    labourRate.trim().length > 0 &&
    Number.isFinite(parsedLabourRate) &&
    parsedLabourRate > 0;
  const reviewedCount = quote
    ? reviewedItems.filter((index) => index < quote.damage_items.length).length
    : 0;
  const customerApprovalToken = window.location.pathname.match(
    /^\/approval\/([A-Za-z0-9_-]+)\/?$/,
  )?.[1];

  if (customerApprovalToken) {
    return <CustomerApprovalPage token={customerApprovalToken} />;
  }

  return (
    <div className="app-shell">
      <aside className="side-rail" aria-label="PanelScan workspace">
        <a className="brand" href="#main-content" aria-label="PanelScan home">
          <span className="brand-mark">
            <Icon name="route" size={22} />
          </span>
          <span className="brand-name">PanelScan</span>
        </a>

        <div className="rail-divider" />

        <button
          className="rail-action"
          type="button"
          onClick={startNewAssessment}
          disabled={busy}
          aria-label="Start a new assessment"
        >
          <span className="rail-action-icon">
            <Icon name="refresh" size={18} />
          </span>
          <span>New assessment</span>
        </button>

        <div className="rail-note">
          <p>Photo + voice in.</p>
          <p>Customer decision out.</p>
        </div>

        <div className="rail-bottom">
          <span className="rail-status-dot" />
          <span>Human review required</span>
        </div>
      </aside>

      <main className="workspace" id="main-content">
        <div className="workspace-topline">
          {quote ? (
            <button
              className="text-button"
              type="button"
              onClick={startNewAssessment}
              disabled={busy}
            >
              Start a new assessment
            </button>
          ) : (
            <span className="topline-status">New assessment</span>
          )}
        </div>

        <section className="intro" aria-labelledby="page-title">
          <div className="intro-copy">
            <h1 id="page-title">From first look to customer response.</h1>
            <p>
              Turn a damage photo and mechanic’s voice note into a reviewed
              estimate the customer can approve or question.
            </p>
          </div>

          <div className="route-map" aria-label="Assessment steps">
            <svg
              className="route-map-line"
              viewBox="0 0 620 60"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <path className="route-base" d="M24 32 H596" />
              <path
                className={`route-progress ${photoComplete ? "is-visible" : ""}`}
                d="M24 32 H215"
              />
              <path
                className={`route-progress ${audioComplete ? "is-visible" : ""}`}
                d="M215 32 H405"
              />
              <path
                className={`route-progress ${quote ? "is-visible" : ""}`}
                d="M405 32 H596"
              />
            </svg>
            <div className="route-stops">
              <div
                className={`route-stop ${
                  photoComplete || quote ? "is-done" : "is-current"
                }`}
              >
                <span className="route-stop-marker" aria-hidden="true">
                  {photoComplete ? <Icon name="check" size={13} /> : <Icon name="camera" size={14} />}
                </span>
                <span>Photo</span>
                <span className="route-stop-detail">SAM 3.1 vision</span>
              </div>
              <div
                className={`route-stop ${
                  audioComplete ? "is-done" : photoComplete ? "is-current" : ""
                }`}
              >
                <span className="route-stop-marker" aria-hidden="true">
                  {audioComplete ? (
                    <Icon name="check" size={13} />
                  ) : (
                    <Icon name="microphone" size={14} />
                  )}
                </span>
                <span>Voice note</span>
                <span className="route-stop-detail">Muse Voice</span>
              </div>
              <div
                className={`route-stop ${
                  quote ? "is-done" : photoComplete && audioComplete ? "is-current" : ""
                }`}
              >
                <span className="route-stop-marker" aria-hidden="true">
                  {quote ? <Icon name="check" size={13} /> : <Icon name="route" size={14} />}
                </span>
                <span>Estimate</span>
                <span className="route-stop-detail">Muse Spark</span>
              </div>
              <div
                className={`route-stop ${
                  approvalToken ? "is-done" : quote ? "is-current" : ""
                }`}
              >
                <span className="route-stop-marker" aria-hidden="true">
                  {approvalToken ? (
                    <Icon name="check" size={13} />
                  ) : (
                    <Icon name="route" size={14} />
                  )}
                </span>
                <span>Customer</span>
                <span className="route-stop-detail">Decision</span>
              </div>
            </div>
          </div>
        </section>

        <section className="evidence-grid" aria-label="Assessment evidence">
          <div className="evidence-section photo-section">
            <div className="section-heading">
              <div>
                <div className="section-title-row">
                  <span className="step-index">1</span>
                  <h2>Damage photo</h2>
                </div>
                <p>SAM 3.1 looks for visible damage.</p>
              </div>
              {photoComplete && (
                <span className="completion-label">
                  <Icon name="check" size={15} />
                  Added
                </span>
              )}
            </div>

            <label
              className={`photo-drop ${draggingPhoto ? "is-dragging" : ""} ${
                preview ? "has-preview" : ""
              }`}
              onDragOver={(event) => {
                event.preventDefault();
                setDraggingPhoto(true);
              }}
              onDragLeave={() => setDraggingPhoto(false)}
              onDrop={handlePhotoDrop}
            >
              <input
                ref={photoInputRef}
                className="visually-hidden"
                type="file"
                accept="image/*"
                capture="environment"
                disabled={busy}
                aria-label="Choose a damage photo"
                onChange={(event) => {
                  pickImage(event.currentTarget.files?.[0]);
                  event.currentTarget.value = "";
                }}
              />
              {preview ? (
                <>
                  <img className="photo-preview" src={preview} alt="Selected damage" />
                  <span className="photo-change">
                    <Icon name="refresh" size={15} />
                    Change photo
                  </span>
                </>
              ) : (
                <span className="photo-empty">
                  <span className="photo-icon">
                    <Icon name="camera" size={25} />
                  </span>
                  <span className="photo-title">Drop a photo here, or browse</span>
                  <span className="photo-hint">
                    Use a clear, well-lit image of the damage.
                  </span>
                  <span className="photo-browse">
                    <Icon name="upload" size={16} />
                    Choose photo
                  </span>
                </span>
              )}
            </label>
            {image && <p className="file-name">{image.name}</p>}
          </div>

          <div className="evidence-section voice-section">
            <div className="section-heading">
              <div>
                <div className="section-title-row">
                  <span className="step-index">2</span>
                  <h2>Voice note</h2>
                </div>
                <p>Muse Voice transcribes the mechanic's note.</p>
              </div>
              {audioComplete && (
                <span className="completion-label">
                  <Icon name="check" size={15} />
                  Added
                </span>
              )}
            </div>

            <div className={`record-surface ${recording ? "is-recording" : ""}`}>
              <button
                className={`record-button ${recording ? "is-recording" : ""}`}
                type="button"
                onClick={toggleRecord}
                disabled={busy}
                aria-pressed={recording}
              >
                <Icon name="microphone" size={19} />
                {recording ? "Stop recording" : "Record voice note"}
              </button>
              <span className="record-status" aria-live="polite">
                {recording
                  ? `Recording ${formatDuration(recordingSeconds)}`
                  : audioComplete
                    ? "Voice note ready"
                    : "Use your device microphone"}
              </span>
            </div>

            <div className="upload-divider">
              <span />
              <span>or upload a recording</span>
              <span />
            </div>

            <label className={`audio-upload ${busy ? "is-disabled" : ""}`}>
              <input
                ref={audioInputRef}
                className="visually-hidden"
                type="file"
                accept="audio/*"
                disabled={busy || recording}
                aria-label="Choose an audio recording"
                onChange={(event) => {
                  pickAudio(event.currentTarget.files?.[0]);
                  event.currentTarget.value = "";
                }}
              />
              <Icon name="upload" size={17} />
              <span>Choose audio file</span>
            </label>

            {audioPreview && (
              <div className="audio-preview">
                <p className="audio-file-name">{audioName}</p>
                <audio controls src={audioPreview}>
                  Your browser does not support audio playback.
                </audio>
              </div>
            )}
            <p className="record-hint">
              Your recording is converted to WAV before transcription.
            </p>
          </div>
        </section>

        <div className="action-row">
          <p className="action-hint">
            {photoComplete && audioComplete
              ? "Both pieces of evidence are ready."
              : "Add a photo and a voice note to continue."}
          </p>
          <button
            className="generate-button"
            type="button"
            onClick={submit}
            disabled={!estimateReady}
          >
            {busy ? "Preparing estimate..." : "Generate estimate"}
            {!busy && <Icon name="route" size={18} />}
          </button>
        </div>

        {error && (
          <div className="error-message" role="alert">
            <Icon name="alert" size={18} />
            <p>{error}</p>
          </div>
        )}

        {busy && (
          <p className="loading-message" role="status" aria-live="polite">
            Preparing your estimate from the photo and voice note...
          </p>
        )}

        {quote && (
          <section className="estimate-result" aria-labelledby="estimate-title">
            <div className="estimate-heading">
              <div>
                <h2 id="estimate-title">Repair estimate</h2>
                <p>{quote.vehicle_summary}</p>
              </div>
              <div className="estimate-actions">
                <span className="workshop-status-stamp">
                  Subject to workshop approval
                </span>
                <button className="copy-button" type="button" onClick={copyDraft}>
                  Copy draft
                </button>
              </div>
            </div>
            {copyStatus && (
              <p className="copy-status" role="status">
                {copyStatus}
              </p>
            )}

            <div className="review-note">
              <Icon name="alert" size={18} />
              <p>
                Review every finding against the photo and voice note. Sharing
                requires workshop approval; parts pricing is not supplier-verified.
              </p>
            </div>

            <div className="source-evidence" aria-label="Evidence used for this estimate">
              <figure className="source-photo">
                <div className="source-photo-image">
                  <img src={preview ?? undefined} alt="Damage photo used for this estimate" />
                </div>
                <figcaption className="source-caption">
                  <span>Damage photo</span>
                  <strong>{image?.name ?? "Source image"}</strong>
                  <small>Visual scan by SAM 3.1</small>
                </figcaption>
              </figure>

              <div className="source-audio">
                <div className="source-audio-heading">
                  <Icon name="microphone" size={18} />
                  <div>
                    <span>Mechanic's voice note</span>
                    <strong>{audioName ?? "Source recording"}</strong>
                  </div>
                </div>
                <audio controls src={audioPreview ?? undefined}>
                  Your browser does not support audio playback.
                </audio>
                <p>Transcribed by Muse Voice</p>
              </div>
            </div>

            <div className="review-progress">
              <div>
                <h3>Check the damage findings</h3>
                <p>
                  Compare each suggestion with the photo and voice note. Checks
                  last for this assessment only.
                </p>
              </div>
              <div className="review-progress-meter">
                <strong>
                  {reviewedCount} of {quote.damage_items.length}
                </strong>
                <progress
                  max={quote.damage_items.length}
                  value={reviewedCount}
                  aria-label={`${reviewedCount} of ${quote.damage_items.length} damage findings reviewed`}
                />
              </div>
            </div>

            <div className="damage-table-wrap">
              <table className="damage-table">
                <thead>
                  <tr>
                    <th scope="col">Vehicle area</th>
                    <th scope="col">Observed damage</th>
                    <th scope="col">Suggested action</th>
                    <th scope="col">Model confidence</th>
                    <th scope="col">Your review</th>
                  </tr>
                </thead>
                <tbody>
                  {quote.damage_items.map((damage, index) => (
                    <tr key={`${damage.panel_name}-${index}`}>
                      <td className="panel-name">{damage.panel_name}</td>
                      <td>{damage.damage_type}</td>
                      <td>
                        <span className="action-tag">
                          {damage.recommended_action === "repair" ? "Repair" : "Replace"}
                        </span>
                      </td>
                      <td>
                        <div className="confidence-cell">
                          <progress
                            max="100"
                            value={Math.round(damage.ai_confidence_score * 100)}
                            aria-label={`${Math.round(damage.ai_confidence_score * 100)} percent model confidence indicator`}
                          />
                          <span>{Math.round(damage.ai_confidence_score * 100)}%</span>
                        </div>
                      </td>
                      <td>
                        <button
                          className={`review-toggle ${
                            reviewedItems.includes(index) ? "is-reviewed" : ""
                          }`}
                          type="button"
                          aria-pressed={reviewedItems.includes(index)}
                          onClick={() => toggleReviewed(index)}
                        >
                          <Icon name="check" size={14} />
                          {reviewedItems.includes(index)
                            ? "Reviewed"
                            : "Mark reviewed"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="estimate-totals">
              <div className="estimate-total">
                <span>Estimated parts</span>
                <strong>{formatCurrency(quote.total_parts_estimate_zar)}</strong>
              </div>
              <div className="estimate-total">
                <span>Estimated labour</span>
                <strong>
                  {quote.total_labor_hours}{" "}
                  {quote.total_labor_hours === 1 ? "hour" : "hours"}
                </strong>
              </div>
            </div>
            {reviewedCount === quote.damage_items.length && (
              <section className="approval-handoff" aria-labelledby="approval-title">
                <div className="approval-handoff-heading">
                  <span className="approval-route-mark" aria-hidden="true">
                    <Icon name="route" size={20} />
                  </span>
                  <div>
                    <h3 id="approval-title">Put the estimate in the customer’s hands</h3>
                    <p>
                      Your reviewed findings become a private approval page.
                      Parts pricing remains an estimate, not a supplier quote.
                    </p>
                  </div>
                </div>

                {!approvalToken && (
                  <div className="approval-rate-row">
                    <label htmlFor="labour-rate">
                      Workshop labour rate
                      <span>Set the rate your shop charges per hour.</span>
                    </label>
                    <div className="approval-rate-input">
                      <span aria-hidden="true">R</span>
                      <input
                        id="labour-rate"
                        type="number"
                        min="0.01"
                        step="0.01"
                        inputMode="decimal"
                        value={labourRate}
                        onChange={(event) => {
                          setLabourRate(event.currentTarget.value);
                          setApprovalError(null);
                        }}
                        aria-describedby="approval-total-note"
                      />
                      <span>/ hour</span>
                    </div>
                    <div className="approval-total-preview" aria-live="polite">
                      <span>Estimated total</span>
                      <strong>
                        {labourRateIsValid
                          ? formatCurrency(
                              quote.total_parts_estimate_zar +
                                quote.total_labor_hours * parsedLabourRate,
                            )
                          : "Set a labour rate"}
                      </strong>
                      <small id="approval-total-note">
                        Parts estimate + {quote.total_labor_hours} labour hours
                        at your rate
                      </small>
                    </div>
                    <button
                      className="approval-primary"
                      type="button"
                      onClick={createApprovalLink}
                      disabled={approvalBusy || !labourRateIsValid}
                    >
                      {approvalBusy
                        ? "Preparing customer estimate…"
                        : "Workshop approve & create customer link"}
                    </button>
                  </div>
                )}

                {approvalToken && (
                  <div className="approval-link-panel">
                    <div>
                      <span className={`approval-state is-${approvalStatus?.status ?? "pending"}`}>
                        {approvalStatus?.status === "approved"
                          ? "Customer approved"
                          : approvalStatus?.status === "changes_requested"
                            ? "Changes requested"
                            : "Waiting for customer"}
                      </span>
                      <p>
                        {approvalStatus?.status === "approved"
                          ? "The customer’s choice is recorded. Confirm the work authorization with them before repairs begin."
                          : approvalStatus?.status === "changes_requested"
                            ? "The customer asked to discuss the estimate. Follow up with them directly."
                            : "Share this private link. It expires after 30 days and records one customer response."}
                      </p>
                    </div>
                    <div className="approval-link-actions">
                      <a
                        className="approval-secondary"
                        href={`/approval/${encodeURIComponent(approvalToken)}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Preview customer page
                      </a>
                      <button
                        className="approval-secondary"
                        type="button"
                        onClick={copyApprovalLink}
                      >
                        Copy private link
                      </button>
                      <button
                        className="approval-secondary"
                        type="button"
                        onClick={refreshApprovalStatus}
                        disabled={approvalBusy}
                      >
                        {approvalBusy ? "Checking…" : "Check response"}
                      </button>
                    </div>
                  </div>
                )}

                {approvalError && (
                  <p className="approval-error" role="alert">
                    {approvalError}
                  </p>
                )}
              </section>
            )}
          </section>
        )}

        <footer className="workspace-footer">
          <span>PanelScan assists with assessment. A qualified person makes the final call.</span>
        </footer>
      </main>
    </div>
  );
}

function CustomerApprovalPage({ token }: { token: string }) {
  const [estimate, setEstimate] = useState<CustomerEstimate | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${API}/api/approvals/${encodeURIComponent(token)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(
            response.status === 404
              ? "This approval link is invalid or has expired. Contact the workshop for an updated estimate."
              : `The estimate could not be loaded (${response.status}).`,
          );
        }
        return (await response.json()) as CustomerEstimate;
      })
      .then((result) => {
        if (active) setEstimate(result);
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(
            caught instanceof Error
              ? caught.message
              : "The estimate could not be loaded.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  async function recordCustomerDecision(
    decision: "approved" | "changes_requested",
  ) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `${API}/api/approvals/${encodeURIComponent(token)}/decision`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision }),
        },
      );
      if (!response.ok) {
        throw new Error(
          response.status === 409
            ? "A response has already been recorded for this estimate. Refresh the page to see it."
            : `Your response could not be recorded (${response.status}).`,
        );
      }
      setEstimate((await response.json()) as CustomerEstimate);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Your response could not be recorded.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="customer-page">
      <header className="customer-header">
        <a className="brand" href="/" aria-label="PanelScan home">
          <span className="brand-mark">
            <Icon name="route" size={22} />
          </span>
          <span className="brand-name">PanelScan</span>
        </a>
        <span>Repair estimate</span>
      </header>

      <div className="customer-content">
        {loading && (
          <p className="customer-loading" role="status">
            Loading the workshop’s estimate…
          </p>
        )}

        {error && !estimate && (
          <section className="customer-error" role="alert">
            <Icon name="alert" size={20} />
            <div>
              <h1>Estimate unavailable</h1>
              <p>{error}</p>
            </div>
          </section>
        )}

        {estimate && (
          <article className="customer-estimate">
            <div className="customer-estimate-header">
              <span className={`approval-state is-${estimate.status}`}>
                {estimate.status === "approved"
                  ? "Workshop-approved · customer approved"
                  : estimate.status === "changes_requested"
                    ? "Workshop-approved · changes requested"
                    : "Workshop-approved · awaiting your response"}
              </span>
              <h1>Repair estimate for your vehicle</h1>
              <p>{estimate.vehicle_summary}</p>
            </div>

            <div className="customer-findings">
              <h2>Proposed repair work</h2>
              {estimate.damage_items.map((damage, index) => (
                <div className="customer-finding" key={`${damage.panel_name}-${index}`}>
                  <div>
                    <strong>{damage.panel_name}</strong>
                    <span>{damage.damage_type}</span>
                  </div>
                  <span className="action-tag">
                    {damage.recommended_action === "repair" ? "Repair" : "Replace"}
                  </span>
                </div>
              ))}
            </div>

            <dl className="customer-costs">
              <div>
                <dt>Estimated parts</dt>
                <dd>{formatCurrency(estimate.total_parts_estimate_zar)}</dd>
              </div>
              <div>
                <dt>
                  Labour estimate
                  <small>
                    {estimate.total_labor_hours} hours ×{" "}
                    {formatCurrency(estimate.labour_rate_zar)} / hour
                  </small>
                </dt>
                <dd>{formatCurrency(estimate.labour_estimate_zar)}</dd>
              </div>
              <div className="customer-grand-total">
                <dt>Estimated total</dt>
                <dd>{formatCurrency(estimate.total_estimate_zar)}</dd>
              </div>
            </dl>

            <p className="customer-disclaimer">
              This estimate has been reviewed and approved by the workshop.
              Parts pricing has not been checked against supplier quotes and may change after
              inspection. Your response records your choice for the workshop;
              it is not an electronic signature and does not authorize work to
              begin.
            </p>

            {estimate.status === "pending" ? (
              <div className="customer-decision">
                <button
                  className="approval-primary"
                  type="button"
                  onClick={() => recordCustomerDecision("approved")}
                  disabled={busy}
                >
                  {busy ? "Recording your response…" : "Approve this estimate"}
                </button>
                <button
                  className="approval-secondary"
                  type="button"
                  onClick={() => recordCustomerDecision("changes_requested")}
                  disabled={busy}
                >
                  Request changes
                </button>
              </div>
            ) : (
              <p className="customer-response" role="status">
                {estimate.status === "approved"
                  ? "Your approval has been recorded. Contact the workshop to confirm the final work authorization."
                  : "Your request has been recorded. Please contact the workshop directly to discuss changes."}
              </p>
            )}

            {error && (
              <p className="approval-error" role="alert">
                {error}
              </p>
            )}
          </article>
        )}
      </div>

      <footer className="customer-footer">
        PanelScan helps workshops prepare estimates. A qualified person makes
        the final repair decision.
      </footer>
    </main>
  );
}
