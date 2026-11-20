# LedgerLens — ECC & Claude Code Project Instructions

## Tech Stack
- **Backend:** Python 3.11+ · FastAPI · Pydantic v2 · SQLite (`backend/schema.sql`, portable to AlloyDB `backend/schema_postgres.sql`) · `google-genai>=1.5`
- **AI Model:** `gemini-3.8-vision-flash` (`GEMINI_PRIMARY_MODEL` & `GEMINI_FLASH_MODEL`) with deterministic offline fallback when `GEMINI_API_KEY` is unset
- **Frontend:** React 19 · Vite 6 · Tailwind CSS 3.4 · Lucide icons (`frontend/src/`)
- **Cloud:** Google Cloud Run (`Dockerfile`, `cloudbuild.yaml`, `deploy/cloudrun.sh`), BigQuery, GCS, Pub/Sub, Vertex AI, Secret Manager

## Core Invariant (Non-Negotiable)
> **Gemini extracts and explains. Deterministic Python rules decide. Immutable workflow tables log. The LLM is never the judge.**

- `backend/app/detect/` MUST remain pure Python `stdlib` only (zero LLM, network, or DB imports).
- `sample_data/` acceptance gate: **6 planted anomalies** (`R1`: 1, `R2`: 1, `R3`: 1, `R4`: 2, `R5`: 1; nominal sum `40531.60`) and **0 false positives** on 4 clean controls (`INV-9001`, `INV-9010`, `INV-9400`, `INV-9500`).

## Build, Test & Verify
- **Backend tests:** `backend/.venv/Scripts/pytest.exe -c backend/pytest.ini backend/tests -q` (Windows)
- **Frontend build:** `npm --prefix frontend run build`
- **Live extraction eval (with key):** `backend/.venv/Scripts/python.exe -m pytest backend/tests/eval_gemini_extraction.py -q`

## Git & Multi-Harness Concurrency Rules
- **Protected `main`:** NEVER commit, push, or merge directly into `main`. Always branch (`feat/`, `fix/`, `docs/`, `chore/`) from `origin/main` and open a PR.
- **Hard Remote Guardrail:** NEVER add or push to `Avani376/Ledgerlens`. Origin is `naughtynova69/LedgerLens-project`.
- **Harness Isolation (Antigravity + ZCode):** Never share a working directory across active harnesses. Claim a dedicated git worktree and non-overlapping file paths via `python scripts/harness_lock.py claim ...` (see `docs/HARNESS_ISOLATION.md`).
- **Session Log:** Read the latest 2 entries in `docs/CONTEXT_LOG.md` at session start and append a concise summary before opening a PR.
