# PanelScan

PanelScan is a 100% newly developed standalone web application built exclusively
for the Meta Global AI Developer Hackathon. This repository was initialized
fresh during the hackathon build period, and all code is net-new.

Voice + vision AI damage assessor: snap a photo, speak the assessment, get an
itemized repair quote.

## Stack

- Frontend: React (Vite, TypeScript) + Tailwind CSS
- Backend: FastAPI (Python)
- AI: SAM 3.1 + Muse Voice Transcribe (Meta Model API), Muse Spark Open
  (open weights, hosted on Modal)

## Structure

- `frontend/` — React + Vite + Tailwind (scaffold with the command below)
- `backend/` — FastAPI service (`app/main.py`, `app/schemas.py`)
- `SCOPE.md` — hackathon scope

## Backend quickstart

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # fill keys, never commit
uvicorn app.main:app --reload --port 8000
```

## Frontend quickstart

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm run dev
```

## Env keys

See `.env.example`: Meta Model API key/base, Modal-hosted Spark Open endpoint,
CORS origins. No secrets in git.
