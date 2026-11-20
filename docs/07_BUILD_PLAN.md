# 07 · Two-Day Build Plan — LedgerLens

Working hours assumed 09:00–22:00 with checkpoints at fixed times. **Sync rule: everyone posts progress in the team chat at every checkpoint, no exceptions.**

## Team roles (adjust names, keep ownership)

| Role | Owns | Primary files |
|------|------|---------------|
| **A · Backend/API lead** | FastAPI app, DB schema, endpoints, audit log | `backend/app/main.py`, `schema.sql`, `db.py` |
| **B · AI integration lead** | Gemini extraction + explanation, prompts, fallback | `backend/app/extract/`, `backend/app/explain/` |
| **C · Detection lead** | R1–R5 rules + unit tests | `backend/app/detect/`, `backend/tests/` |
| **D · Frontend lead** | Dashboard, finding detail, decisions, memo UI | `frontend/` |
| **E · Data & demo lead** | Sample data, normalization, QA, demo video, pitch | `sample_data/`, `backend/app/normalize/` |

Teams of 3: A+C merge, D takes demo/pitch. Teams of 4: D+E merge.

## Day 1 — make the pipeline real

| Time | Track A+B | Track C | Track D | Track E |
|------|-----------|---------|---------|---------|
| 09:00–11:00 | Everyone: setup, read docs 01–07, walk `sample_data/`. **Joint decision: freeze the data model** (docs/03) | | | |
| 11:00–14:00 | A: schema.sql + db.py + /health + upload route. B: Gemini extraction working on ONE PDF | C: `detect/` scaffold, registry, R1 exact-match done | D: Vite app scaffold, dashboard shell, API client | E: normalization functions + vendor-name tests |
| 14:00–15:00 | **Checkpoint 1 — live demo: upload one CSV through the API** | | | |
| 15:00–19:00 | A: findings + decision endpoints. B: extraction on all sample files | C: R1 fuzzy + R3 PO overbilling, with tests | D: findings list + finding detail with evidence panel | E: load sample_data into DB, verify counts |
| 19:00–19:30 | **Checkpoint 2 — R1 finding visible in API response** | | | |
| 19:30–22:00 | A+B: explain stage wired to R1 output | C: R2 contract price | D: severity/amount styling, evidence links | E: demo script draft, start recording setup |

**End of Day 1 bar:** upload → extract → R1/R2/R3 findings in the API. Frontend shows a real findings list.

## Day 2 — make it a product

| Time | Track A+B | Track C | Track D | Track E |
|------|-----------|---------|---------|---------|
| 09:00–12:00 | B: explanation quality pass on all 5 rule types | C: R4 + R5, FP guards, full test suite green | D: decisions (approve/reject) + audit trail UI | E: cross-check all 6 planted anomalies + controls |
| 12:00–12:30 | **Checkpoint 3 — all six sample anomalies detected, zero false positives on controls** | | | |
| 12:30–16:00 | A+B: audit memo endpoint | C: hardening, edge cases | D: memo view, polish, loading/empty states | E: deploy backend to Cloud Run, record demo video |
| 16:00–16:30 | **Checkpoint 4 — feature freeze. Bugs only.** | | | |
| 16:30–19:00 | Full-team bug bash against demo script; run the 2-minute demo 3 times end-to-end | | | |
| 19:00–21:00 | Finalize submission: video, write-up, architecture diagram, pitch slides | | | |
| 21:00–22:00 | Dry run of the pitch; submit early — never submit at the deadline | | | |

## Demo video script (90 seconds — rehearse, do not improvise)

1. **0:00–0:10** "Finance teams leak money through duplicate payments, contract overcharges, and cancelled subscriptions. LedgerLens finds it — and proves it."
2. **0:10–0:30** Upload `sample_data/` → Gemini extracts an invoice PDF into structured JSON on screen.
3. **0:30–0:55** Dashboard: sort by amount at risk. Open the duplicate-payment finding: evidence panel shows both invoices, both payments, the rule that fired, plain-English explanation.
4. **0:55–1:15** Reject the duplicate → decision logged. Open the cancelled-subscription finding → recovery task.
5. **1:15–1:30** One-click audit memo. Close with the ROI line: *"LedgerLens pays for itself from recovered overpayments."*

## Submission checklist (from the event rules)

- [ ] AI-powered product — yes, Gemini extraction + explanation
- [ ] **Deep** Google AI use — structured output, multimodal PDF understanding, function-calling architecture story (not a prompt wrapper)
- [ ] Deployed on Google Cloud (Cloud Run + Secret Manager; Cloud SQL/Storage if time)
- [ ] Real market story: AP automation $2.99B → $7.26B by 2033; quantified leakage stats
- [ ] Scalable architecture diagram (docs/02)
- [ ] Path to a business: recovery-based pricing → SaaS tiers (docs/01 §6)
- [ ] 90-second demo video, deployed product, public repo link

## Risks & fallbacks

| Risk | Fallback |
|------|----------|
| Gemini extraction unreliable on a gnarly PDF | Demo uses clean sample PDFs; CSV path always works |
| Rule fires on clean controls (false positive in demo!) | Tuned thresholds live in rule docstrings — adjust, re-run tests |
| Cloud Run deploy blocked late on Day 2 | Demo locally; deploy is still listed as architecture, mention "one command away" |
| Team blocked on someone | Checkpoint syncs every ~4h; pair, don't wait |
