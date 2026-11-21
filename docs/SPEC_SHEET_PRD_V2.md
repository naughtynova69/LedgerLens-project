# LedgerLens — Technical Spec Sheet & V2 Automation / UI Overhaul PRD

> **Status:** Draft v2.0 (2026-11-21)  
> **Scope:** Current-state architecture audit of `LedgerLens-project`, root-cause diagnosis of UI "AI slop" & manual bottlenecks, and concrete V2 specifications for end-to-end automation and high-craft UI/UX.

---

## 1. How It Is Built Today (Current-State Spec Sheet)

LedgerLens is a **pre-payment neuro-symbolic AP (Accounts Payable) audit gate** built around a strict separation between AI extraction/narration and deterministic Python rule evaluation.

### 1.1 Tech Stack & Repository Layout

| Layer | Technology / Modules | Location |
| :--- | :--- | :--- |
| **Backend API** | FastAPI (`main.py`, 30+ routes), framework-free service layer (`services.py`) | `backend/app/` |
| **Persistence** | SQLite (`db.py`, `schema.sql`) + Postgres adapter (`db_adapter.py`, `schema_postgres.sql`) + SHA-256 hash-chained `audit_log` (`audit_chain.py`) | `backend/app/` |
| **Detection Core** | Pure Python stdlib-only (`detect/types.py`, `detect/registry.py`, `detect/rules/*.py`) — **10 rules (`R1`–`R10`)** | `backend/app/detect/` |
| **Extraction & AI** | Gemini extraction (`extract/`), Gemini CFO explanation + offline fallback (`explain/`), Copilot (`copilot.py`), Agent tools (`skills/agent_tools.py`) | `backend/app/` |
| **Knowledge Graph** | Embedded LadybugDB (`graph/`) powering multi-hop graph rules (`R8`–`R10`) | `backend/app/graph/` |
| **Cloud Integrations** | GCP status, BigQuery sync, Pub/Sub recovery events, Vertex AI routing (`gcp/`) | `backend/app/gcp/` |
| **Frontend** | React 19, Vite 6, Tailwind CSS 3.4, `lucide-react` (`frontend/package.json`) | `frontend/src/` |
| **CI/CD** | GitHub Actions: Python 3.12 `pytest` + AST Neuro-Symbolic Purity Gate + Node 22 Vite build | `.github/workflows/ci.yml` |

### 1.2 Detection Rules (`R1`–`R10`)

| Rule ID | Module | Category |
| :--- | :--- | :--- |
| `R1` | `duplicate.py` | Near-duplicate invoice detection |
| `R2` | `contract_price.py` | Contract price / discount drift |
| `R3` | `po_mismatch.py` | Purchase Order quantity/price mismatch |
| `R4` | `currency_tax.py` | Currency / FX & tax calculation errors |
| `R5` | `cancelled_service.py` | Billing against cancelled/expired services |
| `R6` | `split_po.py` | Split PO threshold circumvention |
| `R7` | `grn_mismatch.py` | Goods Receipt Note (GRN) 3-way match excess qty |
| `R8` | `graph_collusion.py` | Linked vendors / shared bank, email, phone, address |
| `R9` | `graph_cross_entity_duplicate.py` | Cross-entity duplicate billing |
| `R10` | `graph_lineage_credits.py` | Unapplied credit notes / lineage anomalies |

### 1.3 Verified Health & Build Status (Observed 2026-11-21)

- **Frontend (`vitest run`)**: **3 test files passed, 13 tests passed** (`auditVerify.test.jsx`, `smoke.test.jsx`, `copilot.test.jsx`).
- **Backend (`pytest -q`)**: **83 passed, 15 failed, 38 skipped, 4 errors**.
  - **Root cause of failures/errors**: `ladybug` (`_lbug` C extension / `lbug_shared.dll`) is not present in the local Windows `.venv`, causing `RuntimeError: Could not find lbug C API shared library` during `/api/seed/sample_data` and graph rebuilds.

---

## 2. Root-Cause Audit: Why the Website Looks Like "Full AI Slop"

1. **Generic SaaS / AI-Generated Visual Language**
   - Standard `Inter` + `JetBrains Mono` Google Fonts (`index.html`), default Tailwind slate/emerald/red palette (`index.css`, `tailwind.config.js`), generic `lucide-react` icon badges, and uniform `rounded-md` white bordered cards across `FindingsView.jsx`, `Navbar.jsx`, and `UploadView.jsx`.
   - Inline SVG polygon favicon and generic *"Explainable AI Money-Leak Auditor"* `<title>` in `index.html`.
2. **Demo & Prototype Leakage in Production Chrome**
   - `Navbar.jsx` exposes `Seed Demo`, `Demo Guide`, and `GCP · 0/6` pills directly in the primary top bar alongside core workflows.
   - Reviewer identity is hardcoded as `"Vijay (AP Lead)"` in both `FindingsView.jsx` (keyboard shortcuts `a`/`r`/`d`) and `ProofTrailInspector.jsx`.
3. **Orphaned Views & Fragmented Navigation**
   - `Navbar.jsx` only exposes 4 tabs (`Flagged Bills`, `Activity`, `Audit Rules`, `Google Cloud`), while `DashboardView.jsx` and `UploadView.jsx` remain in `frontend/src/views/` as unused/legacy surfaces, and `MemoView.jsx` is buried behind a modal trigger.
   - `UploadView.jsx` still advertises `R1–R5` even though the backend runs `R1–R10`.
4. **Dense, Unprioritized Triage Chrome**
   - A 4-metric KPI strip, segmented status tabs, 11 rule filter chips, search bar, bulk action bar, split-pane list, and multi-tabbed `ProofTrailInspector` + floating `CopilotDrawer` all compete on the same screen without progressive disclosure or editorial typographic hierarchy.

---

## 3. V2 Automation PRD (Zero-Touch Pre-Payment Pipeline)

### 3.1 Problem Statement
Every stage in the current pipeline—uploading files, running extraction, running detection, rebuilding the graph, syncing BigQuery, generating dispute packets, and triaging exceptions—requires **manual user clicks** or separate API calls.

### 3.2 Functional Requirements

| ID | Capability | Current State | Target V2 Automated Behavior |
| :--- | :--- | :--- | :--- |
| **AUTO-1** | **Single-Click / Zero-Click Pipeline** | Separate calls: `/api/ingest/upload` → `/api/run/{id}/extract` → `/api/run/{id}/detect` → `/api/graph/rebuild` | `POST /api/ingest/upload?auto_run=true` (default `true`) triggers an async background pipeline (`extract → normalize → detect → graph → explain`) with real-time SSE/polling job status. |
| **AUTO-2** | **Inbound Watchers & Webhooks** | Manual browser file picker only | Add scheduled folder/GCS bucket poller, email attachment ingest (IMAP/Gmail), and `POST /api/webhooks/erp/{provider}` with SHA-256 idempotency keys. |
| **AUTO-3** | **Scheduled Pay-Run Sweeps** | Ad-hoc manual runs | Configurable cron/Cloud Scheduler job (`POST /api/jobs/payrun-sweep`) before weekly pay runs: runs `R1–R10`, generates the CFO Audit Memo, and dispatches a Slack/Email summary. |
| **AUTO-4** | **Policy-Driven Auto-Disposition** | `_apply_auto_hold_policy` only mutates `recommended_action` to `HOLD_PAYMENT` | Auto-clear clean/low-risk batches (`AUTO_APPROVED`), auto-generate & queue dispute packets (`GET /api/findings/{id}/dispute-packet`) for high-confidence `R1`/`R5` findings, and emit outbound ERP payment-block webhooks. |
| **AUTO-5** | **Graceful Graph & Local Test Automation** | Missing `lbug_shared.dll` crashes `/api/seed/sample_data` on Windows | Add a graceful degraded/in-memory fallback in `backend/app/graph/` when native `ladybug` is unavailable (logging a warning and skipping `R8`–`R10` rather than crashing), and auto-run `setup_lbug_native.py` in dev setup scripts. |
| **AUTO-6** | **Automated UI Quality Gates** | Vitest unit tests only (no visual/a11y/E2E CI gate) | Add Playwright E2E + axe-core a11y + visual regression checks in `.github/workflows/ci.yml` enforced against the installed Vercel `web-design-guidelines` skill. |

---

## 4. V2 UI/UX Overhaul Spec (Eliminating "AI Slop")

Using the newly installed Vercel Agent Skills (`web-design-guidelines`, `react-best-practices`, `composition-patterns`, `react-view-transitions`):

1. **Dedicated Design System & Editorial Ledger Aesthetic**
   - Replace generic SaaS cards with a crisp **financial-ledger / terminal** hierarchy: tight tabular alignment, clear typographic scale (distinct display/heading vs. dense mono figures), deliberate whitespace, and restrained semantic color (only for actual financial risk/hold states).
   - Remove hardcoded `"Vijay (AP Lead)"` strings; bind actor identity to workspace/session auth context.
   - Move `Seed Demo` and `Demo Guide` out of the primary `Navbar.jsx` into an explicit **Developer / Sandbox** mode banner or workspace switcher menu.
2. **Unified Information Architecture**
   - Consolidate orphaned views (`DashboardView.jsx`, `UploadView.jsx`, `MemoView.jsx`) into clean, purposeful routes/tabs: **Pay Run Queue** (triage + inline proof), **Batch & Connectors** (automated feeds + quarantined `NeedsReviewDrawer`), **Executive Memo**, **Audit Trail**, and **Policy & Rules (`R1`–`R10`)**.
3. **Component & React Hygiene**
   - Apply `react-best-practices` and `composition-patterns`: eliminate prop-drilling in `App.jsx` (379 lines of top-level state), split `FindingsView.jsx` (545 lines) and `ProofTrailInspector.jsx` (536 lines) into focused composable subcomponents, and add smooth `react-view-transitions` between queue selection and detail inspection.

---

## 5. Installed Vercel Agent Skills (Local Antigravity Setup)

The `skills/` folder from `vercel-labs/agent-skills` has been downloaded locally to:
- `C:\LedgerLens\.agents\skills\`
- `C:\LedgerLens\LedgerLens-project\.agents\skills\`

Included skills:
- `web-design-guidelines`
- `react-best-practices`
- `composition-patterns`
- `react-view-transitions`
- `deploy-to-vercel`
- `vercel-cli-with-tokens`
- `vercel-optimize`
- `writing-guidelines`
- `react-native-skills`
