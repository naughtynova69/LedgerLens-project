# LedgerLens — Project Mind Map & Accuracy Roadmap

> **Plain-English Summary:** LedgerLens is a **pre-payment audit gate** for mid-market finance teams (`$20M–$500M` supplier spend) and CA/audit firms. You upload exported CSVs or PDF/image invoices, **Gemini 3.8 Vision Flash** extracts structured fields, **pure Python rules (`R1`–`R5`)** catch duplicates/overcharges/tax/cancelled-service leaks with deterministic math, and **Gemini 3.8 Vision Flash** turns that proof into a CFO-ready explanation before money leaves the bank.

---

## 1. Visual Mind Map: What Is Done vs. What Is Next

```mermaid
flowchart LR
    ROOT["LedgerLens<br/>Pre-Payment Audit Gate"]

    ROOT --> DONE["DONE (MVP + Cloud Ready)"]
    ROOT --> NEXT["TO DO NEXT (Pilot & Scale)"]

    DONE --> D1["1. Ingestion & Extraction<br/>CSV/PDF/Image Upload + 1-Click Demo Seed<br/>Gemini 3.8 Vision Flash + Offline Fallback<br/>Line-Total Math Check (±0.05)"]
    DONE --> D2["2. Pure Python Rules (R1-R5)<br/>R1 Duplicate/Near-Duplicate<br/>R2 Contract Price Drift<br/>R3 PO Qty/Premature/Unordered<br/>R4 Currency/Tax/FX Drift<br/>R5 Cancelled Service/Vendor/PO<br/>6/6 Sample Anomalies + 0 False Positives"]
    DONE --> D3["3. CFO Explainability & Actions<br/>proof_trail-Grounded Narrative<br/>Approve/Reject/Recovery/Request Docs<br/>1-Click Dispute Email + CSV Export<br/>CFO Audit Memo (.md + JSON)"]
    DONE --> D4["4. Minimalist Finance UI<br/>Exceptions (4 KPIs + Split Inspector)<br/>Activity (Batches + Immutable Audit Log)<br/>Cloud & Policy (GCP + Thresholds)"]
    DONE --> D5["5. Cloud & Governance<br/>Dockerfile + cloudbuild.yaml + cloudrun.sh<br/>BigQuery / AlloyDB / GCS / PubSub / Secret Mgr<br/>Protected main + PR Workflow + CONTEXT_LOG"]

    NEXT --> N1["1. Boost Gemini 3.8 Vision Flash Accuracy<br/>Run live eval_gemini_extraction.py with API key<br/>300-DPI PDF->PNG + contrast/deskew<br/>1-Retry Math-Repair Loop on mismatch<br/>Indian GST + Multi-Currency Few-Shot Prompts<br/>15-20 Noisy PDF Golden Benchmark"]
    NEXT --> N2["2. Live Cloud Deployment<br/>Run deploy/setup_gcp.sh + cloudrun.sh<br/>Verify Vertex AI + BigQuery + GCS live"]
    NEXT --> N3["3. Pilot & Distribution Wedge<br/>48-Hour Historical Leak Diagnostic<br/>CA / Audit Firm Multi-Tenant Workspace<br/>Live Daily FX API + R6/R7 Rules"]
```

---

## 2. How to Increase `Gemini 3.8 Vision Flash` Vision & Extraction Accuracy

Because LedgerLens already has `verify_extracted_line_totals()` (`backend/app/extract/gemini_extract.py`) and `backend/tests/eval_gemini_extraction.py`, you can improve vision accuracy systematically:

1. **Measure First with Live Eval (`eval_gemini_extraction.py`):**
   - Set `GEMINI_API_KEY` in `backend/.env` and run `pytest backend/tests/eval_gemini_extraction.py` to get a real baseline score instead of guessing.
2. **Pre-Process PDFs & Scans Before Sending to Vision:**
   - Render PDFs at `250–300 DPI` PNGs, auto-rotate/deskew crooked scans, and apply light contrast sharpening for faded thermal/scanned bills before calling `gemini-3.8-vision-flash`.
3. **Add a 1-Retry Deterministic Self-Correction Loop:**
   - Today, `verify_extracted_line_totals()` flags mismatches (`qty * unit_price * (1 + tax_pct/100) != line_total`) as `needs_review`.
   - Upgrade: when a line fails the math check, automatically send **one targeted repair call** back to `gemini-3.8-vision-flash` with the exact discrepancy (`"Extracted qty=6, unit_price=465, tax=18%, total=3100 — re-read line 1 carefully"`), and only fall back to `needs_review` if the second pass still fails.
4. **Indian GST & Multi-Currency Few-Shot Grounding:**
   - Keep `temperature=0` + `response_schema`, and add 2–3 compact examples in the extraction prompt showing `CGST + SGST = 18%` vs `IGST`, `₹ / Rs. / INR`, `€ / EUR`, `$ / USD`, and `PO-XXXX` references so line tax and currency fields never drift.
5. **Build a 15–20 Document Golden Test Set:**
   - Collect tricky real-world invoices (multi-page PDFs, stamped/handwritten totals, multi-tax tables, foreign currency) in `sample_data/eval_pdfs/` and score field-level F1 (`invoice_number`, `vendor_name`, `currency`, `tax_pct`, `line_total`) on every prompt or preprocessing change.
