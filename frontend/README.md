# LedgerLens Frontend

Modern, production-ready React 19 + Vite + Tailwind CSS dashboard for the LedgerLens explainable spend auditor.

Backend API: `docs/05_API_SPEC.md` · Data model: `docs/03_DATA_MODEL.md` · Rules: `docs/04_DETECTION_RULES.md`.

---

## Quickstart

```bash
cd frontend
npm install
npm run dev
# -> http://localhost:5173
```

To build for production:

```bash
npm run build
```

---

## Features & Views

1. **Executive Overview (`/dashboard`)**:
   - Spend exposure KPI cards (Total at Risk, Audited Spend, Recovered / Blocked, Exception Count).
   - Category breakdown across all 5 deterministic audit rules (R1 to R5).
   - Live high-risk exception feed with one-click drill down.
   - Quick actions: "Load Demo Data", "Run Detect", "Audit Memo".

2. **Exception Queue (`/findings`)**:
   - Comprehensive multi-filter queue (Search keywords, Severity, Rule Category, Review Status).
   - Sortable columns by Amount at risk, Confidence, and Rule.
   - Real-time filtered spend exposure calculation.
   - One-click inspection of evidence and proof trails.

3. **Finding Detail & Evidence Observatory (Modal View)**:
   - **Explainability Card**: CFO-ready headline, plain-English narrative, recommended actions, and auditor verification limitations.
   - **Side-by-Side Source Records**: Live comparison tables of invoice lines, governing contracts, authorized purchase orders, and settled payment vouchers.
   - **Evidence Chips**: Immutable `EvidenceRef` chips displaying exact record IDs, fields, and values.
   - **Reviewer Action Workflow**: Instant decision buttons (Approve, Block/Reject, Request Vendor Docs, Raise Recovery Task) with required audit justification.
   - **Audit Trail**: History of all previous reviewer decisions, timestamps, and notes.

4. **Document Ingest & Spend Data Center (`/upload`)**:
   - 4 Dedicated drag-and-drop dropzones for Invoices, Purchase Orders, Vendor Contracts, and Bank Payments (CSV/PDF).
   - Ingestion status feedback with row counts.
   - 1-Click "Load 5 Demo Sample Files" shortcut.
   - Batch pipeline tracking table (`Ready for Audit` → `Detection Verified`).

5. **Executive Audit Memo (`/memo`)**:
   - Professional executive briefing format.
   - Deterministic exposure breakdown by rule.
   - "Copy Markdown" to clipboard with toast notification.
   - "Print / Export PDF" layout.

6. **Detection Engine Architecture (`/rules`)**:
   - Deep dive into R1–R5 deterministic algorithms, pseudocode, and mathematical formulas.
   - Explains why deterministic verification prevents AI hallucinations.

7. **Governance & Audit Log (`/audit`)**:
   - Tamper-evident log of all reviewer decisions and ledger modifications.

---

## Design System & Tokens

- **Theme**: Obsidian canvas (`#090D16`), deep card surfaces (`#0D1424` / `#111A2E`), elevated subtle borders (`#1F293D`).
- **Brand Accent**: Emerald audit glow (`#10B981`) and Electric Cyan (`#06B6D4`).
- **Financial Severity Tokens**:
  - `Critical`: Crimson Rose (`#F43F5E`)
  - `High`: Warm Amber (`#F59E0B`)
  - `Medium`: Electric Sky (`#0EA5E9`)
  - `Low`: Neutral Slate (`#94A3B8`)
- **Typography**: Inter for crisp reading hierarchy; tabular JetBrains Mono for exact currency amounts and IDs.
