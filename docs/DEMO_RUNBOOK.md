# LedgerLens — 3-Minute Buildathon Live Demo Runbook

**Event:** Google DeepMind & Google Cloud Startup Buildathon India 2026  
**Team:** Team Builders (Leader: Vijay)  
**Target Time:** 3:00 minutes (strict pacing)

---

## Pre-Demo Verification Checklist (60 seconds before stage)
1. Confirm backend + frontend unified server is live (`GET /health` → `{"status":"ok"}`).
2. Confirm `GEMINI_PRIMARY_MODEL=gemini-3.8-vision-flash` and `GEMINI_FLASH_MODEL=gemini-3.8-vision-flash` are set in `.env` (note: deterministic offline fallback runs smoothly even without a live API key).
3. Ensure browser starts on `/` with a clean or freshly seeded database (`Load Demo Dataset` resets deterministically).

---

## 0:00–0:35 — Hook & Problem Statement
- **Narrative:**
  > *"Mid-market finance teams (\$20M–\$500M annual supplier spend) and CA/audit firms face silent AP leakage: fuzzy duplicate invoices, contract price drift, PO overbilling, FX/tax errors, and cancelled-service charges."*
  > *"Manual invoice checks cost ~\$10 and take 10+ days per invoice (PRGX). Exact-match ERPs miss tweaked invoice numbers like `INV-8821` to `INV-8821-R2`, post-payment audits recover only 0.1% (PRGX) vs. 0.2%–0.35% pre-payment savings (Xelix / Duplo), and black-box AI alerts fail because no CFO will freeze a vendor payment on an opaque anomaly score."*
  > *"LedgerLens is a **pre-payment neuro-symbolic audit gate before every pay run**, landing with a zero-ERP **48-hour Historical Leak Diagnostic** wedge: Gemini extracts and explains, deterministic Python rules decide, and every finding ships with a line-level proof trail."*

---

## 0:35–1:45 — Live LedgerLens Walkthrough
1. **Seed & Detect (`0:35–0:50`):**
   - Click **"Load Demo Dataset (6 Planted Anomalies)"** in the Top Command Bar.
   - Highlight the **4 KPI Cards**: `Total Spend Audited`, `Total Money at Risk (₹40,531.60)`, `Open Exceptions (6)`, and `Recovered / Blocked (₹0.00)`.
   - Note that 4 clean control invoices (`INV-9001`, `INV-9010`, `INV-9400`, `INV-9500`) produced **zero false positives**.
2. **Split-View Proof Trail Explorer (`0:50–1:20`):**
   - Open **Exception Queue** and click **`R1 Duplicate` (`INV-8821` vs `INV-8821-R2`)**:
     - Show the **3-Way Evidence Diff Card**, payment settlement links (`PAY-5001`, `PAY-5002`), and **Proof Math** bar (`line_similarity=1.0`, `date_gap_days=2`).
     - Point directly to the attribution badge: **`Decision: Deterministic Rule R1 · Narrative: Gemini 3.8 Vision Flash`**.
   - Click **`R2 Price` (`INV-9102`)**:
     - Show `INV-9102` billed `₹465.00` vs Contract `C-001` `₹420.00`, even though `PO-1006` wrongly approved `₹465.00` — proving **the contract governs**.
3. **Human Decision, Audit Log & CFO Memo (`1:20–1:45`):**
   - Enter an audit note (e.g., *"Confirmed duplicate with Sunbeam Electricals; clawback issued"*) and click **"Hold / Recover"**.
   - Show live KPI update (`Recovered / Blocked` jumps immediately).
   - Click **Audit Log** tab to show the chronological `ingest → detect → recovery` record.
   - Click **CFO Audit Memo** tab and click **Download `.md`** (or Copy Markdown) to show the board-ready report.

---

## 1:45–2:30 — Architecture & Google AI Stack Proof
- **Walk through the Neuro-Symbolic Stack:**
  1. **Ingest & Extract (`POST /api/run/{batch_id}/extract`):** Routes PDFs/contracts and high-volume batch/CSV workloads to **`gemini-3.8-vision-flash`** (`GEMINI_PRIMARY_MODEL` / `GEMINI_FLASH_MODEL`) using strict Pydantic JSON schemas (`ExtractedInvoicePayload`) + deterministic line-total verification (`qty * unit_price * (1 + tax_pct/100)`).
  2. **Pure Deterministic Judge (`backend/app/detect/`):** Zero LLM imports and zero network calls. Evaluates `R1`–`R5`, computes confidence scores and `amount_at_risk`, and emits `proof_trail` JSON + standardized `recommended_action` (`HOLD_PAYMENT`, `REQUEST_CREDIT_NOTE`, `DISPUTE_VENDOR`, `CANCEL_AUTOPAY`).
  3. **Explain & Google Agent Skills (`backend/app/explain/`, `backend/app/skills/`):** Gemini narrates strictly from `proof_trail` and invokes structured function tools (`fetch_payment_records`, `generate_audit_memo`, `route_recovery_task`).
  4. **Cross-Harness Readiness:** Built with `AGENTS.md` + isolated worktrees and synced with Google AI Studio JSON schemas (`docs/ai_studio_schemas/`) for Google Antigravity IDE evaluation.

---

## 2:30–3:00 — Enterprise ROI & Cloud Run Production Scaling
- **ROI Pitch:** Moving mid-market finance teams (\$20M–\$500M spend) and CA/audit firms from 0.1% post-payment recovery (PRGX) to **0.2%–0.35% pre-payment savings** (Xelix / Duplo)—while cutting ~\$10 / 10+ day per-invoice manual review (PRGX)—starts with a zero-ERP **48-hour Historical Leak Diagnostic** wedge and scales into **pre-payment protection before every pay run**.
- **Google Cloud Production Path (`Dockerfile`, `cloudbuild.yaml`, `deploy/cloudrun.sh`):**
  - **Compute:** Unified multi-stage container on **Google Cloud Run** (`uvicorn` serving FastAPI + React SPA).
  - **AI & Secrets:** **Vertex AI / Gemini 3.8 Vision Flash** + **Secret Manager** (`GEMINI_API_KEY`).
  - **Persistence:** SQLite (`backend/schema.sql`) swaps cleanly to **Cloud SQL**, and local `uploads/` swaps to **Google Cloud Storage**.
