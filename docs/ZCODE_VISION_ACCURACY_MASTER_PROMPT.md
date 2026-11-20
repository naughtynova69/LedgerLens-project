# ZCode (`GLM 5.3`) Master Prompt — Gemini 3.8 Vision Flash Accuracy Upgrade

> **How to use:** Paste the **Master Prompt** below directly into **ZCode (`GLM 5.3`)**. It enforces LedgerLens's neuro-symbolic invariants, isolates ZCode into its own git worktree (`wt-zcode-vision-accuracy`) via `scripts/harness_lock.py`, and upgrades `gemini-3.8-vision-flash` extraction accuracy for LedgerLens's mid-market / Indian AP audit niche.

---

## Copy-Paste Master Prompt for ZCode (`GLM 5.3`)

```text
You are ZCode (GLM 5.3) working on LedgerLens-project (c:\LedgerLens\LedgerLens-project).
Antigravity (Gemini) is working concurrently on other parts of the repo. Follow strict harness isolation:

### 1. Mandatory Harness Isolation & Git Setup (Run First)
1. Check active locks:
   python C:\LedgerLens\LedgerLens-project\scripts\harness_lock.py status
2. Create an isolated git worktree from origin/main (NEVER work in main or Antigravity's worktree):
   git -C C:\LedgerLens\LedgerLens-project fetch origin
   git -C C:\LedgerLens\LedgerLens-project worktree add C:\LedgerLens\wt-zcode-vision-accuracy -b feat/gemini-38-vision-accuracy origin/main
3. Claim your non-overlapping file paths:
   python C:\LedgerLens\LedgerLens-project\scripts\harness_lock.py claim --harness zcode --branch feat/gemini-38-vision-accuracy --worktree C:\LedgerLens\wt-zcode-vision-accuracy --paths backend/app/extract backend/tests/test_extract.py backend/tests/eval_gemini_extraction.py
4. Do ALL file reads, edits, and tests inside C:\LedgerLens\wt-zcode-vision-accuracy. NEVER edit outside your claimed paths, NEVER push to main, NEVER touch Avani376/Ledgerlens.

### 2. Core Neuro-Symbolic Invariant
- Gemini extracts and explains; deterministic Python rules (backend/app/detect/) decide; immutable tables log.
- Extraction MUST remain fail-closed (missing invoice_number or grand_total, or line-total math mismatch > 0.05 -> flag needs_review).
- Zero-key offline deterministic fallback (mode="mock_fallback") MUST continue passing all tests without GEMINI_API_KEY.

### 3. Your Task: Upgrade Gemini 3.8 Vision Flash Extraction Accuracy
Update `EXTRACTION_SYSTEM_PROMPT` and the extraction pipeline in `backend/app/extract/gemini_extract.py` (using `gemini-3.8-vision-flash` for all vision/PDF/image/CSV extraction) to maximize accuracy on mid-market & Indian B2B AP documents:

A. Replace `EXTRACTION_SYSTEM_PROMPT` with this domain-tuned prompt:
"""
You are a high-precision accounts-payable document extraction engine for an audit-grade financial system.
Extract ONLY fields literally visible in the document (PDF, scan, image, or CSV). NEVER guess, extrapolate, or invent missing values—return null for any unreadable or absent field.

Domain & Formatting Rules:
1. Dates: Normalize all dates (DD/MM/YYYY, DD-MMM-YYYY, YYYY/MM/DD, etc.) to strict ISO-8601 `YYYY-MM-DD`.
2. Currency: Output ISO-4217 3-letter codes (`INR`, `USD`, `EUR`, `GBP`). Map `₹`, `Rs.`, `Rs`, `INR` -> `INR`; `$`, `US$` -> `USD`; `€` -> `EUR`; `£` -> `GBP`.
3. Numbers & Indian Comma Grouping: Strip currency symbols and thousand separators (including Indian lakh/crore grouping like `1,23,456.00` -> `123456.00`). Return plain decimals.
4. Invoice & Revision Numbers: Preserve exact suffixes and revision markers (e.g., `INV-8821-R2`, `CN-104`, `PO-1006`)—never strip `-R2` or `/FY26` suffixes.
5. Tax & GST Handling:
   - Combine split Indian GST components (`CGST 9% + SGST 9%` -> `tax_pct: 18.0`; `IGST 18%` -> `tax_pct: 18.0`).
   - Do NOT treat TDS (Tax Deducted at Source) as invoice GST/tax or subtract TDS from `line_total` / `grand_total`.
   - If a line is explicitly tax-exempt / zero-rated (`0%`, `Exempt`, `Nil`), set `tax_pct: 0.0`.
6. Line Items & Multi-Page Tables:
   - Extract every billable line item in order (`line_no` 1..N). Ignore subtotals, page headers/footers, and bank-detail blocks.
   - Ignore HSN/SAC codes as item names; extract the actual item/service description into `item`.
   - If `unit_price` is pre-tax and `line_total` is post-tax, ensure `round(quantity * unit_price * (1 + tax_pct / 100), 2) == line_total`.
   - If `discount_pct` or `discount_applied_pct` is shown on the invoice or contract line, capture it accurately.
7. Cross-Document References: Capture `vendor_name`, `vendor_id` (if printed), `po_id` / PO number, `contract_id`, and `payment_status` / `credited` indicators verbatim when present.
8. Scan Quality: If a stamp, watermark, or low-DPI region obscures a number, return `null` rather than guessing so the fail-closed verifier flags `needs_review`.
"""

B. Add High-Accuracy Extraction Safeguards in `backend/app/extract/gemini_extract.py`:
1. **1-Retry Arithmetic Self-Correction (Live Mode Only):**
   - After `_generate_with_model(...)` returns for `invoices`, run `verify_extracted_line_totals(lines)`.
   - If warnings are non-empty AND live Gemini credentials are active, perform at most **1 targeted retry** passing the previous JSON + exact mismatch warnings (e.g., `Line 1 expected X vs extracted Y; re-read quantity, unit_price, tax_pct, and line_total from the document`) at `temperature=0`.
   - Re-run `verify_extracted_line_totals(...)` on the retry output; if warnings persist, keep the warnings so the batch transitions to `needs_review` (fail-closed).
2. **PDF / Image Media Resolution Hint:**
   - When `mime_type` is `application/pdf` or `image/*`, pass `media_resolution` (if supported by the installed `google-genai` `GenerateContentConfig`, guarded cleanly with `getattr` / `hasattr` so older SDK versions or mocks never break) at high resolution for dense invoice tables.
3. **Tests & Eval Coverage (`backend/tests/test_extract.py`, `backend/tests/eval_gemini_extraction.py`):**
   - Add unit tests for:
     - Indian GST (`CGST 9% + SGST 9%`) & Indian comma formatting (`1,23,456.00`) normalization/extraction.
     - The 1-retry arithmetic repair path (mocking `_generate_with_model` to fail math on call 1 and succeed on call 2, plus verifying it stops after 1 retry when still mismatched).
     - Preserving offline `mock_fallback` behavior when `GEMINI_API_KEY` is unset.

### 4. Verification & PR Handoff
1. Run:
   C:\LedgerLens\LedgerLens-project\backend\.venv\Scripts\pytest.exe -c backend\pytest.ini backend\tests -q
   npm --prefix frontend run build
2. Commit on `feat/gemini-38-vision-accuracy`, push to `origin`, open a PR to `main`, and release your lock:
   python C:\LedgerLens\LedgerLens-project\scripts\harness_lock.py release --harness zcode
```
