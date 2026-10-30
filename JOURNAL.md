# PanelScan — Build Journal

Running log: what was done, errors hit, and how they were fixed.

## 2026-10-30 — Environment setup (first attempts)

- Did: oriented in workspace (`/home/jay`, no git repo at root). User chose new
  Desktop folder, undecided stack, scope to be pasted.
- Error: shell sandbox broken — no working `bwrap`, every command failed before
  starting. Fix: reran with one-time elevated (unsandboxed) approval.
- Error: first elevated run rejected by user. Fix: scaffolded docs via file
  tools only, deferred git/venv until approval.

## 2026-10-30 — Scope review (original PanelScan plan)

- Did: reviewed pasted scope (voice+vision quote builder, FastAPI + Supabase +
  React admin suite) against hackathon rules/dates.
- Found: applications closed Oct 25 (user must already be accepted); scope
  confused track vs theme ("Build for Your World" is a theme, tracks are
  Indie/Startup); missing technical-background half of selection criteria;
  scope claimed existing Supabase tables but the admin suite used localStorage.
- Fix: rewrote scope with correct track/theme, background section, Supabase
  bypass (JSON prefill), explicit agent loop for bonus categories.

## 2026-10-30 — ADMIN-HJR hands-off rule

- User directive: never touch the live `ADMIN-HJR` suite. Honored since:
  only two read-only reads ever, zero writes, and integration reframed as
  manual prefill by the owner.

## 2026-10-30 — First repo + backend plumbing (abandoned later, see pivot)

- Did: `Desktop/PanelScan/`, git init, Python 3.10 venv, requirements
  installed, FastAPI stub → full routing with Pydantic schemas, Meta + Modal
  clients, 4 pytest tests.
- Error: elevated approvals got disabled mid-session; smoke-test call denied.
  Fix: user re-enabled via "retry commits".
- Error: ruff B008 on `File(...)` defaults (FastAPI idiom false positive).
  Fix: `# noqa: B008` + follow-up commit. Final state: 4 passed, ruff clean.

## 2026-10-30 — STRATEGIC PIVOT: hard reset to net-new repo

- Why: hackathon "new work only" rule — abandoned `PanelScan/` and all legacy
  ties, started `PanelScan-Hackathon/` from scratch.
- Did: fresh git repo (root `4d8cab6`), README + SCOPE with net-new
  declaration, redesigned schema (`DamageItem`/`QuoteEstimate` with
  per-panel `ai_confidence_score`).
- Note: old folder left in place, not deleted.

## 2026-10-30 — Backend engine & API clients (this phase)

- Did: net-new `main.py` (CORS, MIME/size validation, parallel Meta calls →
  Modal agent → `QuoteEstimate`), `meta_client.py` (transcribe + segment with
  shared multipart helper + demo fallbacks), `modal_client.py` (schema-bound
  agent prompt + response validation), fresh pytest suite.
- Frontend not scaffolded yet at time of writing — `App.tsx` upload UI
  provided as code for the user to drop in after running the Vite commands.

## 2026-10-30 — Production architecture: Modal app, Meta URLs, frontend

- Did: net-new `backend/modal_app.py` (vLLM + `guided_json` schema
  enforcement, `fastapi_endpoint` webhook); Meta client pointed at
  `https://api.meta.ai/v1` with model IDs `muse-voice-transcribe-1.0` /
  `sam-3.1` and env-overridable endpoint paths; scaffolded the missing
  Vite + Tailwind frontend and wrote the upload UI into `App.tsx`.
- Error: user reported Vite/Tailwind setup complete, but no `frontend/`
  existed anywhere on disk. Fix: scaffolded it directly
  (`npm create vite`, Tailwind v3, config + CSS wiring) and verified.
- Caution: Meta endpoint *paths* are not confirmed from official docs —
  base URL + model IDs corroborated by multiple community sources only.
  Must verify at `https://dev.meta.ai/docs` before the demo. Paths are
  env-overridable (`VOICE_ENDPOINT_PATH`, `SAM_ENDPOINT_PATH`).
- Caution: `MODEL_ID` in `modal_app.py` is a FILL-ME placeholder until the
  exact Spark Open weights repo is confirmed from hackathon materials.
