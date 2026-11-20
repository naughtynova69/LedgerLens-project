# LedgerLens — Session Context Log

> **Purpose:** Compact, append-only handoff log so any AI harness (**ZCode / GLM 5.3**, **Antigravity / Gemini**, **Claude Code**, **Codex**, **Cursor**) or human contributor can resume work in <500 tokens without re-reading the entire codebase or conversation history.
>
> **Rule:** Read the latest 2 entries at session start; append a concise entry before opening your PR.

---

## Current Project Snapshot (Baseline)

| Item | Current State |
|---|---|
| **GitHub Origin** | `https://github.com/naughtynova69/LedgerLens-project` (`main` protected via `Protect main` ruleset #27733621) |
| **Hard Git Guardrail** | NEVER add/push to `Avani376/Ledgerlens`. NEVER push or merge directly into `main`; always branch & open a PR. |
| **Models** | `GEMINI_PRIMARY_MODEL=gemini-3.8-vision-flash` · `GEMINI_FLASH_MODEL=gemini-3.8-vision-flash` (offline deterministic fallback active when key unset) |
| **Neuro-Symbolic Invariant** | `backend/app/detect/` is pure Python `stdlib` only (zero LLM/DB/network imports). |
| **Sample Data Gate** | `sample_data/` yields **6 findings** (`R1`: 1, `R2`: 1, `R3`: 1, `R4`: 2, `R5`: 1; nominal sum `40531.60`) and **0 false positives** on 4 clean controls (`INV-9001`, `INV-9010`, `INV-9400`, `INV-9500`). |
| **UI Architecture** | Minimalist 3-surface Finance UI (`Exceptions`, `Activity`, `Cloud & Policy`) in `frontend/src/` (React 19 + Vite 6 + Tailwind 3.4). |
| **GCP Integrations** | BigQuery (`ledgerlens_analytics`), AlloyDB for PostgreSQL (`schema_postgres.sql`), GCS, Vertex AI, Secret Manager, Pub/Sub (`backend/app/gcp/`). |
| **Verification Baseline** | `backend/.venv/Scripts/pytest.exe -c backend/pytest.ini backend/tests -q` (`51 passed, 1 skipped`); `npm --prefix frontend run build` (`0 errors`). |

---

## Session History

### 2026-11-20 — Master Prompts 0–4 + Minimalist Finance UI & GCP Integration
- **Merged to `main` (`f624933`):** Full extraction (`POST /api/run/{batch_id}/extract`), pure `R1`–`R5` rules with `proof_trail`, CFO explanation layer + Agent Skills, Split-View Proof Trail Inspector, Cloud Run `Dockerfile` + `cloudbuild.yaml`, AI Studio schemas + eval harness, Minimalist 3-surface Finance UI, GCP helpers (`backend/app/gcp/`), Finance workflows (`backend/app/finance/`), and `docs/GCP_INTEGRATION_GUIDE.md`.

### 2026-11-20 — GitHub Governance, Branch Protection & Harness PR Workflow
- **PR #1 (`docs/add-prd` → `main`, `7bc3611`):** Added `docs/PRD.md`.
- **Repo Ruleset (`Protect main`, ID `27733621`):** Blocked deletions, force-pushes, and direct pushes to `main`; PR required before merge.
- **PR #2 (`docs/agent-pr-workflow` → `main`, `e758e3f`):** Added `docs/AGENT_PR_WORKFLOW.md` and updated `README.md` + `AGENTS.md` for ZCode (`GLM 5.3`), Antigravity (`Gemini`), and all other harnesses.
- **PR #3 (`docs/readme-badges` → `main`, `4e09332`):** Upgraded `README.md` with Shields.io badges and Documentation Index.

### 2026-11-20 — ICP / Business Model Refinement, Gemini 3.8 Vision Flash & Context Log
- **Branch:** `docs/icp-business-model-and-context-log`
- **Changes:**
  - Narrowed ICP to mid-market finance teams (`$20M–$500M` annual supplier spend) and CA / audit firms using CSV/PDF exports before weekly pay runs, with a 48-hour Historical Leak Diagnostic wedge.
  - Replaced uncited `$5B / $240B` and `61%` claims with cited benchmarks: `0.1%` post-payment recovery (PRGX), `0.2%–0.35%` pre-payment savings (Xelix / Duplo), `~$10` / `10+ days` per invoice (PRGX), and `$6.94B -> $12.46B` (2026–2031, `12.44%` CAGR, Mordor Intelligence) / `$2.99B` software-only (DataM Intelligence).
  - Documented Hybrid Wedge → Recurring Pre-Payment SaaS + CA/Audit Firm channel (`85%–92%+` gross margin).
  - Aligned `GEMINI_FLASH_MODEL` default to `gemini-3.8-vision-flash` across config, `.env.example`, and all docs.
  - Created `docs/CONTEXT_LOG.md` and added token-efficient multi-agent + session-log rules to `AGENTS.md`.
- **Open Next Steps:** Review & merge PR for `docs/icp-business-model-and-context-log`; optionally run live `GEMINI_API_KEY` extraction eval (`backend/tests/eval_gemini_extraction.py`) and deploy to Cloud Run via `deploy/setup_gcp.sh` + `deploy/cloudrun.sh`.

### 2026-11-21 — Unify on Gemini 3.8 Vision Flash + Project Mind Map
- **Branch:** `chore/use-gemini-38-vision-flash`
- **Changes:**
  - Replaced `gemini-4-carbon` with `gemini-3.8-vision-flash` across backend config, extraction, frontend attribution badges, Dockerfile/Cloud Run scripts, and all docs.
  - Added [docs/PROJECT_MINDMAP.md](docs/PROJECT_MINDMAP.md) with a plain-English project overview, Done vs. To-Do mind map, and 5-step `Gemini 3.8 Vision Flash` accuracy playbook.
- **Open Next Steps:** Merge PR for `chore/use-gemini-38-vision-flash`, run live `eval_gemini_extraction.py` with `GEMINI_API_KEY`, and implement PDF 300-DPI preprocessing + 1-retry math-repair loop.

### 2026-11-21 — ZCode: Gemini 3.8 Vision Flash Accuracy (Domain Prompt + 1-Retry Math Repair)
- **Branch / PR:** `feat/gemini-38-vision-accuracy` → PR #9
- **Changes:**
  - Replaced `EXTRACTION_SYSTEM_PROMPT` in `backend/app/extract/gemini_extract.py` with a **locale-aware** AP prompt covering US / Canada / UK-EU / Western markets AND India: regional date conventions (US MM/DD, EU/India DD/MM, DE/CH DD.MM.YYYY + disambiguation), ISO-4217 mapping incl. `C$`→CAD / `A$`→AUD / `NZ$`→NZD, US-UK + Indian lakh/crore + European decimal-comma + Swiss apostrophe number grouping, revision-suffix preservation, tax generalization (India CGST+SGST/IGST + TDS; Canada GST+QST/HST; US Sales Tax; EU VAT/MwSt./TVA/IVA/BTW; zero-rated/Exempt/Nil/Reverse charge → 0.0), Western tax IDs (GSTIN/VAT No./EIN/BN), French/German/Spanish/Italian/Dutch label mapping, scan-quality fail-closed.
  - Added live **1-retry arithmetic self-correction** (`_extract_invoice_payload_live` + `build_arithmetic_retry_feedback`, `MAX_ARITHMETIC_RETRIES=1`): line-total mismatches fed back once at temperature 0; persisting warnings keep `needs_review` (fail-closed). `extract_invoice` now returns `verification_warnings` too.
  - Added guarded `media_resolution=MEDIA_RESOLUTION_HIGH` for PDF/image `GenerateContentConfig` (getattr-safe for older SDKs/mocks).
  - Offline mock fallback hardened to match: `_plain_decimal` parses US/Indian/EU/Swiss number formats; `_normalize_tax_pct` combines split tax (3-decimal rates like QST 9.975% kept), maps exempt/nil/reverse-charge to 0.0, never sums TDS; `_normalize_extracted_currency` maps C$/A$/NZ$; `_normalize_extracted_date` adds DD.MM.YYYY (shared `normalize.py` untouched — outside claimed paths).
  - 16 new tests in `backend/tests/test_extract.py` + 2 live locale evals (Indian GST, US format) in `backend/tests/eval_gemini_extraction.py` (`RUN_LIVE_GEMINI_EVAL=1`-gated).
- **Checks:** `pytest` (66 passed, 3 skipped), `npm --prefix frontend run build` (0 errors)
- **Open Next Steps:** Merge PR #9; run live locale evals with `GEMINI_API_KEY` + `RUN_LIVE_GEMINI_EVAL=1`; optionally add PDF 300-DPI preprocessing upstream of extraction and extend `normalize.py` (`%d.%m.%Y` dates, C$ currency map) when paths are free.

---

## Append Template (Copy for Future Sessions)

```markdown
### YYYY-MM-DD — <Short Session Title>
- **Branch / PR:** `<branch>` → PR #<n>
- **Changes:** <1–3 bullets with key file paths>
- **Checks:** `pytest` (<count>), `npm --prefix frontend run build` (<status>)
- **Open Next Steps:** <1–2 concrete items>
```
