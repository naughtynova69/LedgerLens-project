# LedgerLens — Agent & Repository Guidelines (`AGENTS.md`)

## 1. Repository & Git Guardrails
- **Target GitHub Repository:** `https://github.com/naughtynova69/LedgerLens-project` (GitHub account: `naughtynova69`)
- **HARD GUARDRAIL:** NEVER add `Avani376/Ledgerlens` as a git remote, NEVER push to `Avani376`, and NEVER import its git history.
- **Branch Protection Convention:** Keep `main` always green and deployable. `main` is protected on GitHub (`Protect main` ruleset). All AI harnesses and models — including **ZCode (`GLM 5.3`)**, **Antigravity (`Gemini`)**, **Claude Code**, **Codex**, and **Cursor** — MUST follow [docs/AGENT_PR_WORKFLOW.md](docs/AGENT_PR_WORKFLOW.md): perform all work on dedicated `feat/`, `fix/`, `docs/`, or `chore/` branches, push only to that branch, and open a **Pull Request to `main`** for the repository owner to merge. NEVER commit, push, or auto-merge directly into `main`.

## 2. Core Neuro-Symbolic Invariant (Non-Negotiable)
> **Gemini extracts and explains. Deterministic Python rules decide. Immutable workflow tables log.**
> **The LLM is NEVER the judge.**

- `backend/app/detect/` MUST remain **pure deterministic Python** (`stdlib` only) with ZERO LLM SDK imports (`google`, `genai`, `openai`, etc.) and ZERO network or database calls.
- Every finding emitted by rules `R1`–`R5` MUST carry a deterministic `proof_trail` JSON payload (`rule_id`, `severity`, `amount_at_risk`, `currency`, `confidence`, `entity_refs`, `evidence`, `math`, `recommended_action`).
- `sample_data/` acceptance invariant: running detection against `sample_data/` MUST detect all **6 planted anomalies** (`R1`: 1, `R2`: 1, `R3`: 1, `R4`: 2, `R5`: 1; total `₹40,531.60` nominal sum across currencies / `40531.60`) with **0 false positives** on the 4 clean control invoices (`INV-9001`, `INV-9010`, `INV-9400`, `INV-9500`).

## 3. Tech Stack & Model Configuration
- **Backend:** Python 3.11+ · FastAPI · Pydantic v2 · SQLite (`backend/schema.sql`, portable to Cloud SQL) · `google-genai>=1.5`.
- **Frontend:** React 19 · Vite 6 · Tailwind CSS 3.4 · Lucide icons.
- **Model Env Config (never hardcode keys or legacy models):**
  - `GEMINI_PRIMARY_MODEL=gemini-4-carbon` (multimodal extraction + CFO-ready explanation)
  - `GEMINI_FLASH_MODEL=gemini-3.8-vision-flash` (high-volume batch/vision extraction routing)
  - `GEMINI_API_KEY=` (stored in `backend/.env` locally or Google Secret Manager in Cloud Run; offline deterministic fallback/mock mode MUST work when unset).

## 4. Multi-Agent, Token Efficiency & Session Context Log Rules
- **Session Context Log:** Read the latest 2 entries in [docs/CONTEXT_LOG.md](docs/CONTEXT_LOG.md) at session start, and append a concise summary entry before opening your PR so future sessions resume without re-reading the repo.
- **Sustainable Token-Efficient Multi-Agent Split:** Use at most **3 concurrent** worker subagents (`flash` tier for routine doc/copy/test edits) in isolated scopes with strictly non-overlapping owned file paths; keep prompts concise and use targeted `rg` + line-range reads instead of full-file reads.
- Maximum **3 concurrent** worker subagents, each in an isolated git worktree (`git worktree add ../ledgerlens-tN-<slug> -b <branch> origin/main`) with strictly non-overlapping owned file paths.
- Worker subagents commit locally to their own branches and MUST NEVER push, open PRs, edit outside owned paths, or leave background dev servers (`uvicorn` / `vite`) running.
- Central orchestrator reviews diffs, wires shared integration points (`backend/app/main.py`, `backend/app/services.py`), merges in dependency order (`T1` → `T2` → `T3`), removes temporary worktrees, and runs full `pytest` + live HTTP smoke verification.

## 5. Single Design Owner Rule (UI/UX)
- Keep a **single design owner** for frontend UI/UX passes — never stack parallel UI redesign agents concurrently.
- Follow the institutional fintech forensic workstation aesthetic (crisp off-white canvas, tabular monospace numerals, Crimson/Amber/Indigo/Emerald semantic badges).
- Verify live UI behavior and visual layout via Browser Use / browser subagent QA before closing UI branches.
