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

### 2026-11-21 — Startup Buildathon Deck Fix & Regeneration (ZCode)
- **Branch:** `docs/fix-buildathon-ppt`
- **Changes:**
  - Added deterministic `python-pptx` generator `docs/presentation/build_deck.py` plus official-template branding assets (`docs/presentation/assets/`) extracted from the original submission PDF.
  - Regenerated the 7-slide submission deck (`LedgerLens_Startup_Buildathon_Submission.pptx` + exported PDF): removed uncited `$5B / $240B / 61%` claims in favor of cited benchmarks (PRGX / Xelix / Duplo / Ardent Partners / Mordor Intelligence — full URLs in speaker notes); replaced broken soft-hyphen glyphs with plain ASCII hyphens + clean en-dashes; aligned every deck fact to shipped code (`R1`–`R5`, `24` API routes, `gemini-3.8-vision-flash` as the unified primary/batch model per `backend/.env.example`, AlloyDB / BigQuery / GCS / Pub-Sub / Cloud Run, Agent Skills); closing slide now carries live proof (6 planted anomalies, `₹40,531.60`, 0 false positives, 51 tests) and repo links.
  - Consolidated `docs/presentation/assets/` to the three images the generator uses (`header_strip.png`, `brand_block.png`, `graphics_collage.png`), replacing the four raw PDF-extracted intermediates merged via PR #8.
- **Checks:** deck-level QA only (layout overflow/overlap scan + `pdftotext` content gates); no backend/frontend code touched — `pytest` and `npm run build` unaffected.
- **Open Next Steps:** Merge PR for `docs/fix-buildathon-ppt` (deck already reflects the unified `gemini-3.8-vision-flash` config from PR #7); replace `[Live Cloud Run URL]` on the closing slide after the first Cloud Run deploy.

---

## Append Template (Copy for Future Sessions)

```markdown
### YYYY-MM-DD — <Short Session Title>
- **Branch / PR:** `<branch>` → PR #<n>
- **Changes:** <1–3 bullets with key file paths>
- **Checks:** `pytest` (<count>), `npm --prefix frontend run build` (<status>)
- **Open Next Steps:** <1–2 concrete items>
```
