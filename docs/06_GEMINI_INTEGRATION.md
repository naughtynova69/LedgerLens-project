# 06 · Gemini Integration Guide

LedgerLens uses Gemini in exactly **two** places — extraction and explanation. Detection is deterministic. If you find yourself asking Gemini "is this invoice suspicious?", stop: that is a rule, not a prompt.

## 1. Where Gemini is used

| Stage | Model | Mode | Output |
|-------|-------|------|--------|
| `extract/` | `GEMINI_PRIMARY_MODEL` (`gemini-4-carbon` default; `GEMINI_FLASH_MODEL` `gemini-2.5-flash` for high-volume batch routing) | **Structured output** (JSON schema) + multimodal input (PDF/images) | Canonical invoice/contract JSON (schemas in `extract/schemas.py`) |
| `explain/` | `GEMINI_PRIMARY_MODEL` (`gemini-4-carbon` default) | **Structured output** (JSON schema) | `{headline, explanation, recommended_action, confidence_label, limitations}` |

Also fine to mention in the pitch: function calling (`backend/app/skills/`) wraps `fetch_payment_records`, `generate_audit_memo`, and `route_recovery_task` for ERP/workflow integration.

## 2. Setup

1. Get a key: **https://aistudio.google.com/apikey** (free tier is enough for the MVP).
2. Put it in `backend/.env` (never in code, never in git):
   ```
   GEMINI_API_KEY=AIza...
   GEMINI_PRIMARY_MODEL=gemini-4-carbon
   GEMINI_FLASH_MODEL=gemini-2.5-flash
   ```
3. SDK (already in `requirements.txt`):
   ```python
   from google import genai
   client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
   ```

## 3. Extraction prompt (extract stage — keep temperature 0)

System instruction:

```
You are a data-entry engine for an accounts-payable audit system.
Extract fields from the provided invoice/contract document.
Return ONLY what is literally present in the document — never guess,
never infer missing values (leave them empty strings / null).
Follow the provided JSON schema exactly.
Currency codes are ISO-4217 (e.g. INR, USD, EUR).
Dates are YYYY-MM-DD.
If the document is a scan, read it; if a field is unreadable, return null.
```

User turn: the uploaded file (PDF/image/CSV text). Response is constrained by `response_mime_type="application/json"` + `response_schema=INVOICE_SCHEMA` so parsing never depends on regex.

**Extraction reliability rules:**
- `temperature=0` for extraction; ≤0.3 for explanation.
- Fail closed: if `invoice.number` or `grand_total` is null → quarantine the record with `needs_review`, don't silently drop it.
- Log raw Gemini response + parsed JSON side by side for the audit trail.

## 4. Explanation prompt (explain stage)

System instruction:

```
You write findings for a corporate finance team. Input is a JSON finding
produced by a deterministic audit rule, with evidence references.
Rules:
- Explain in plain language a CFO can forward to procurement.
- Cite evidence fields exactly as given (record IDs, amounts). NEVER invent
  or recompute amounts, dates, or IDs — you are the narrator, not the judge.
- Structure: headline (≤12 words), explanation (3-6 sentences referencing
  the rule and evidence), recommended_action (1-2 sentences), limitations
  (what a human must confirm).
- Tone: precise, neutral, no scare words like "fraud" — say "duplicate risk".
```

Why this works: the rule already decided *what* happened, *how much* is at risk, and *how confident* it is. Gemini only packages it. This keeps every number in the UI traceable to `findings` table fields.

## 5. Audit memo (optional Gemini polish)

The memo body (totals, findings, decisions) is generated **deterministically** from the DB. Gemini may rewrite only the opening executive-summary paragraph, given the same "never invent numbers" system instruction.

## 6. Function calling (mention in architecture; build only if time remains)

Gemini can propose structured tool calls — e.g. `lookup_vendor_master(vendor_name)`, `fetch_po(po_id)` — against ERP/doc systems. For the MVP we call our own DB directly; document the function-calling design in the pitch as the production integration path.

## 7. Cost & latency tips

- Primary model (`GEMINI_PRIMARY_MODEL=gemini-4-carbon`) handles multimodal PDF/scan extraction and CFO explanations; `GEMINI_FLASH_MODEL=gemini-2.5-flash` handles high-volume batch/CSV extraction routing.
- Cache extraction results — re-running detect must **not** re-call Gemini.
- Budget: the whole demo dataset is ~15 files → well inside free tier.

## 8. No-key fallback (so the demo never dies)

`extract/` and `explain/` degrade gracefully: with no `GEMINI_API_KEY`, `extract/` runs deterministic CSV extraction plus an offline text/mock PDF fallback (`mode="mock_fallback"`) validated against the Pydantic schemas, and `explain/` returns a deterministic CFO-ready card grounded in `proof_trail` with `"generated_without_gemini": true`. The dashboard, rules, and workflow work offline without a key.
