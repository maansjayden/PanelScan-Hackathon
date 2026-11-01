# PanelScan — Scope

PanelScan is a 100% newly developed standalone web application built exclusively
for the Meta Global AI Developer Hackathon. This repository was initialized
fresh during the hackathon build period, and all code is net-new.

Event: Meta Global AI Developer Hackathon
Track: Indie Developer
Theme: Build for Your World
Bonus targets: Best Agentic Use-Case, Best Build on Meta Open Weight Models

## 1. Problem (firsthand)

Panel-beating quotes are manual: walk the car, handwritten notes, look up
parts, type the quote. Slow, error-prone, breaks flow on the shop floor.

## 2. Solution

A standalone web app: snap a photo of the damage, speak the assessment aloud,
receive an itemized AI-generated repair quote with per-panel confidence,
ready to review and export.

Demo line: "2021 VW T-Cross. Front bumper is gone, left fender needs panel
beating, headlight assembly is cracked." → photo + voice → quote.

## 3. Builder background

Software Engineering student at WeThinkCode_, specializing in Data Engineering.

Recent AI builds:

- Umlimi: offline-first PWA for maize disease detection using a MobileNetV3
  int8 model and ONNX Runtime.
- Netgrade: passive security posture scanner using an async Python engine and
  FastAPI.
- Aegis: zero-trust execution boundary and cryptographic ledger for AI agents.

## 4. How Meta models are used

- SAM 3.1 (Meta Model API): visual segmentation of damage / affected panels.
- Muse Voice Transcribe (Meta Model API): transcription of noisy shop-floor
  audio. Browser recordings and uploads are converted to mono 24 kHz PCM WAV
  for the documented transcription endpoint.
- Muse Spark (`muse-spark-1.3`, Meta Model API): agentic core. Receives
  SAM 3.1 output + voice transcript and returns the strict JSON quote.

Agent loop: SAM 3.1 (vision) + Muse Voice (transcription) → Muse Spark via
Responses API (synthesis) → Pydantic-validated JSON quote. The three model
calls are made server-side; the image and audio are never sent to a browser
provider integration.

## 5. Architecture

React (Vite) → FastAPI `POST /api/assess-damage` (multipart image+audio) →
parallel SAM 3.1 + Voice Transcribe → Muse Spark Responses API (original image,
transcript, and compact SAM boxes) → strict JSON `QuoteEstimate` → displayed
in the app for review.

## 6. MVP scope (Nov 4)

- One photo + one voice memo → one `QuoteEstimate`.
- Strict JSON contract: vehicle_summary, damage_items[] (panel_name,
  damage_type, recommended_action, ai_confidence_score),
  total_parts_estimate_zar, total_labor_hours.
- Works on one real car in the ≤3 min demo video.
- Explicit demo mode returns deterministic sample data when deliberately
  enabled; model/API failures are reported rather than silently replaced.
- Estimates require human review and do not represent supplier-verified prices.

Out of scope: video stream, multi-car batch, payments, parts ordering.

## 7. Risks + mitigations

- Noisy audio → Voice Transcribe + short structured utterances + manual edit.
- SAM output is special-token geometry rather than panel labels → pass its
  bounding boxes and the original image with the transcript to Muse Spark;
  omit large mask payloads and validate the estimate server-side.
- Model/API failure → return a clear service error; use deterministic data only
  when `PANELSCAN_DEMO_MODE=true`.
- Muse Spark hosting and latency → use Meta Model API rather than the
  unconfigured Muse Spark Open/Modal draft.

## 8. Submission checklist

- [x] Track: Indie Developer / Theme: Build for Your World
- [x] Meta Model API adapters use the documented Voice, Responses, and image
  request formats.
- [ ] Configure a Meta Model API key and verify a live end-to-end assessment.
- [ ] Muse Spark Open bonus path (not part of the current hosted Model API
  implementation).
- [ ] Demo video ≤3 min, live car, voice + photo → quote
- [ ] Repo runs from README, no secrets committed
