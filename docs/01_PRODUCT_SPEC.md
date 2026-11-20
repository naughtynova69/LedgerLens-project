# 01 · Product Spec — LedgerLens

> One-line pitch: **LedgerLens is a pre-payment neuro-symbolic AI "money-leak auditor" for mid-market finance teams (\$20M–\$500M annual supplier spend) and CA/audit firms that gates every pay run to stop duplicate payments, contract price drift, PO overbilling, FX/tax errors, and cancelled-service charges before disbursement—with line-level proof trails.**

## 1. Vision & Problem Statement

Mid-market finance teams (\$20M–\$500M annual supplier spend) and CA/audit firms face structural Accounts Payable leakage—fuzzy duplicate invoices, contract price drift, PO overbilling, FX/tax errors, and cancelled-service charges. Industry benchmarks show manual invoice processing costs ~\$10 and takes 10+ days per invoice (PRGX), and post-payment recovery audits recover only 0.1% of spend (PRGX), whereas pre-payment prevention delivers 0.2%–0.35% savings on outbound spend (Xelix / Duplo). Exact-match ERP checks miss tweaked invoice numbers, and black-box AI alerts lack the verifiable proof finance teams require before blocking payment.

Core principle: **Gemini extracts and explains; deterministic Python rules decide; every finding carries a verifiable line-level proof trail.**

LedgerLens operates as a **pre-payment audit gate before every pay run**, comparing **contracts, purchase orders, invoices, payments, and vendor master data** to stop leakage before money leaves the bank. To remove adoption friction, LedgerLens enters via a **48-hour Historical Leak Diagnostic**—a zero-ERP onboarding wedge on exported CSV/PDF batches that proves ROI on past spend before gating live pay runs.

## 2. Users (personas)

| Persona | What they do in LedgerLens | What they care about |
|---------|---------------------------|----------------------|
| **AP analyst** | Works the exception queue: opens findings, inspects evidence, approves/rejects, requests documents | Fast triage, no false alarms, one screen to decide |
| **Finance controller / CFO** | Reads the dashboard, forwards findings to procurement, reads the audit memo | Total money at risk, audit-ready proof, plain language |
| **Procurement lead** | Receives escalated findings, negotiates with vendors | Fair findings with contract references |
| **Internal auditor** | Reviews decision logs and the audit memo | Complete, immutable trail |

## 3. MVP scope (two days — this is a hard boundary)

| In scope ✅ | Out of scope ❌ |
|------------|----------------|
| Upload invoices / POs / contracts / payment ledger as CSV & PDF | ERP connectors (SAP, Oracle, NetSuite, QuickBooks) |
| Gemini extraction of PDF/scan fields into structured JSON | Autonomous payments or payment execution |
| Deterministic normalization layer (names, SKUs, currency, tax codes) | Real-time bank feeds |
| Five detection rules (R1–R5) | More detection rules, ML scoring models |
| Exception dashboard with severity, amount at risk, evidence links, explanation | Multi-tenant orgs & RBAC (single demo login is fine) |
| Approve / reject / request-docs with an audit log | Full workflow engine |
| One-click audit memo (markdown/PDF text) | Scheduled continuous monitoring jobs |

**Why this boundary:** the value and defensibility are in *detection + explanation + workflow*. Everything else is distraction for a 2-day build.

## 4. User stories (the demo is built from these)

1. **Upload** — *As an AP analyst, I upload `invoices.csv` + a PDF invoice, so LedgerLens can audit them.*
2. **Extract** — *As AP analyst, I see the PDF invoice turned into structured line items, so I trust the data is captured.*
3. **Triage** — *As AP analyst, I open the findings queue sorted by amount at risk, so I fix the expensive problems first.*
4. **Verify** — *As AP analyst, I click a finding and see the invoice lines, PO line, contract clause, and payment record side by side, so I can confirm it without opening five systems.*
5. **Act** — *As AP analyst, I reject a duplicate payment and mark it "recovery task", so the log shows who decided what and when.*
6. **Report** — *As CFO, I click "Generate audit memo" and get a one-page summary of total money at risk and top findings, so I can forward it to leadership.*

## 5. Demo success criteria (definition of a great demo)

- Upload → findings on screen in **under 2 minutes** using `sample_data/`.
- The six planted anomalies in `sample_data/` are **all detected**; the clean control invoices produce **zero** findings.
- Every finding on screen shows: severity, amount at risk, evidence links, plain-English explanation, recommended action.
- Approve/reject works and is logged.
- Audit memo generates in one click.

## 6. Business model (for the pitch, not for code)

| Tier | Model |
|------|-------|
| Pilot / Wedge | **48-hour Historical Leak Diagnostic** (zero-ERP CSV/PDF export wedge) → converts to pre-payment pay-run gating |
| SaaS | Per entity / per invoice volume / per seat |
| Enterprise | ERP integrations, multi-currency, audit logs, custom policy rules, SOC 2 controls |
| Expansion modules | Procurement compliance, vendor-risk monitoring, tax recovery, contract-renewal savings |

Beachhead: mid-market finance teams (\$20M–\$500M annual supplier spend) and CA/audit firms via the 48-hour Historical Leak Diagnostic → expanding into pre-payment pay-run gating across multi-ERP, multi-currency enterprises.

## 7. Metrics that matter (quote these to judges)

- ₹/$ at risk found vs. ₹/$ recovered (the ROI line)
- False-positive rate per rule (explainability keeps it discussable)
- Time-to-decision per finding
- % findings with complete evidence trail (target: 100%)
