# PanelScan

PanelScan turns a vehicle-damage photo and a mechanic's voice memo into an
itemized repair estimate for workshop staff to review, approve, and share for a
customer decision.

## Stack

- Frontend: React, Vite, TypeScript, and Tailwind CSS
- Backend: FastAPI
- Models: Muse Voice Transcribe, SAM 3.1, and Muse Spark via Meta Model API

Every estimate is subject to workshop approval. Parts prices and labour hours
are not verified supplier quotes. After checking every finding, the workshop
enters its own hourly labour rate and explicitly approves the estimate before
creating a private customer-approval link. Customer decisions are recorded in
the backend; customer approval does not represent an electronic signature or
authorize work to begin.

## Run locally

1. Create a Meta Model API key from the [Meta Model API dashboard](https://dev.meta.ai/).
2. Copy `.env.example` to `.env` in the repository root and set `MODEL_API_KEY`.
   Keep `.env` private; it is ignored by Git.
3. Start the backend:

   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```

4. In another terminal, start the frontend:

   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

5. Open the Vite URL shown in the frontend terminal. Allow microphone access,
   add a damage photo, record or upload a voice memo, and generate an estimate.
   Review and correct every finding, enter the shop's hourly labour rate, then
   approve the estimate and create a customer link. The customer can approve
   the workshop-reviewed estimate or request changes; return to the workshop
   screen and check for the response.

The frontend defaults to `http://localhost:8000` for the backend. To use a
different host or port, set `VITE_API_URL` in `frontend/.env.local`.

The browser converts recordings and uploaded audio to mono 24 kHz PCM WAV before
sending them to the backend. The backend checks that format before forwarding
the file to Muse Voice Transcribe.

Approval links expire after 30 days and accept one customer response. The
backend stores only the estimate, workshop labour rate, and response; it does
not persist the uploaded photo or recording. By default, approval records are
stored in `backend/data/approvals.sqlite3` (ignored by Git). Set
`PANELSCAN_APPROVALS_DB` to a persistent local path when you need approval
records to survive deployments or restarts.

This is a hackathon workflow prototype, not an e-signature service, payment
system, or repair authorization system. The customer should confirm final
authorization directly with the workshop before repairs begin.

## Demo mode

To run without an API key, set `PANELSCAN_DEMO_MODE=true` in `.env`. The API
returns clearly logged, deterministic sample data instead of calling Meta. The
default is `false`; missing credentials are reported rather than silently
producing a demo estimate.

## Project layout

- `frontend/` — photo/audio capture and estimate display
- `backend/app/main.py` — upload validation and assessment orchestration
- `backend/app/services/meta_client.py` — Muse Voice Transcribe and SAM 3.1
- `backend/app/services/muse_client.py` — Muse Spark quote agent
- `backend/app/approvals.py` — private-token estimate approval records
- `SCOPE.md` — hackathon scope and current architecture
