# 04 · Detection Rules — the explainable core

This is the most important engineering document in the repo. Every rule here must be:
**deterministic** (same input → same finding), **evidence-carrying** (cites record IDs + field values), and **confidence-scored** (by the rule, not by Gemini). Together they power LedgerLens's **pre-payment gate before every pay run**, as well as the **48-hour Historical Leak Diagnostic** zero-ERP onboarding wedge for mid-market finance teams (\$20M–\$500M annual supplier spend) and CA/audit firms.

## 0. Rule engine contract

Each rule is a pure function in `backend/app/detect/rules/`:

```python
@register("R1")
def detect_duplicates(ctx: DetectionContext) -> list[Finding]: ...
```

- `DetectionContext` carries normalized lists: `invoices, payments, purchase_orders, contracts, vendors`.
- Rules **never** touch the DB, network, or Gemini. That keeps them unit-testable and citable.
- Every `Finding` carries: `rule_id, title, severity, amount_at_risk, currency, entity_refs, evidence[], confidence, summary`.

**Severity scale**

| Severity | Meaning |
|----------|---------|
| `critical` | Money already lost (duplicate paid twice, charge paid after cancellation) — recovery candidate |
| `high` | Confirmed mismatch, not yet paid — block before payment |
| `medium` | Policy/pricing deviation needing human confirmation |
| `low` | Informational (e.g. near-threshold drift) |

---

## R1 — Duplicate & near-duplicate invoices

- **Intent:** same invoice resubmitted with altered invoice numbers, dates, or vendor-name formatting. Exact-match ERP checks miss tweaked invoice numbers, so fuzzy matching in a **pre-payment gate before every pay run** is mandatory—capturing **0.2%–0.35% pre-payment savings** (Xelix / Duplo) vs. **0.1% post-payment recovery** (PRGX) while avoiding **~\$10 and 10+ days per invoice** of manual rework (PRGX).
- **Logic (MVP):**
  ```
  group invoices by normalized vendor_id
  for each pair (A, B) with different invoice_number:
      amount_ok   = |grand_total_A - grand_total_B| / grand_total_A <= 0.005
      line_sim    = jaccard( {(item, qty, unit_price)} of A, B )
      num_sim     = SequenceMatcher(invoice_number_A, invoice_number_B).ratio()
      date_gap    = |invoice_date_A - invoice_date_B| <= 30 days
      if amount_ok and line_sim >= 0.8 and (num_sim >= 0.6 or date_gap):
          emit finding, confidence = weighted(amount_ok, line_sim, num_sim)
  ```
- **Severity:** `critical` if **both** invoices are paid (money already gone); `high` if only one/unpaid.
- **Evidence:** both invoice numbers, dates, grand totals, per-line similarity, linked payment IDs.
- **Example from sample_data:** `INV-8821` (2026-10-14) vs `INV-8821-R2` (2026-10-16), Sunbeam Electricals, ₹4,956.00 each, both paid → **critical, ₹4,956 at risk**.
- **False-positive guards:** ignore pairs where one invoice has status `credited` (legitimate revised invoice); require line similarity, not just same total (two genuine identical-price orders must differ on date_gap + num_sim before flagging).

## R2 — Contract price leakage

- **Intent:** invoiced unit price above the negotiated contract rate; missed agreed discounts; violated payment terms.
- **Logic:**
  ```
  join invoice line → contract line on (vendor_id, normalized item) where contract.status = 'active'
  and contract covers invoice_date
  if unit_price > contracted_unit_price:
      emit; amount_at_risk = (unit_price - contracted_unit_price) * quantity * (1 + tax_pct/100)
  if payment_terms of invoice != contract payment_terms: emit low-severity finding
  ```
- **Precedence note:** the **contract governs**. If the PO also carries the wrong price (see sample PO-1006 @ 465), R2 still fires against the contract — that is the point.
- **Severity:** `high` if unpaid (blockable), `critical` if paid.
- **Evidence:** invoice line (unit_price), contract line (contracted_unit_price), delta × qty.
- **Example:** `INV-9102` bills LED Panel @ ₹465 vs contract C-001 @ ₹420 → ₹318.60 at risk on 6 units.
- **FP guards:** exact item match after normalization only; skip when no contract exists for the item (PO governs that case — see R3).

## R3 — PO mismatch & overbilling

- **Intent:** billed above PO quantity, billed before delivery, billed for items not on the PO, billed above PO unit price.
- **Logic:**
  ```
  sum(invoice qty) per (po_id, normalized item)
  if summed qty > po.quantity                      -> overbilling: amount_at_risk = excess * po.unit_price * (1 + tax)
  if invoice_date < po.expected_delivery           -> billed-before-delivery (medium)
  if item not on PO at all                         -> unbilled-item (high)
  if invoice unit_price > po unit_price            -> po price breach (medium; R2 handles contract level)
  ```
- **Severity:** `high` for quantity overbilling; `medium` for timing/price drift.
- **Example:** `INV-9155` bills 60 × A4 Paper against PO-1008 quantity 50 → 10 boxes over → **₹2,832.00 at risk**. (The earlier legitimate order `INV-9010` on PO-1002 for exactly 50 proves the sum-first FP guard matters.)
- **FP guards:** allow partial billing across several invoices (sum first, then compare); skip POs with status `cancelled` (that case belongs to R5).

## R4 — Currency & tax errors

- **Intent:** wrong currency, bad FX conversion, invalid/duplicate tax charges, tax where exemption applies.
- **Logic:**
  ```
  if invoice.currency != po.currency (same item):            currency-mismatch (high)
  if payment.fx_rate_to_inr deviates > 2% from reference:    fx-error (high; at-risk = delta on paid amount)
  if invoice.tax_pct != contract.tax_pct for the item:       tax-error (amount_at_risk = tax delta)
  if same (invoice, item) appears twice with tax:            duplicate-tax-line (high)
  ```
- **Reference FX rate for the MVP demo:** a constant table in `normalize/` (e.g. `USD→INR = 88.0`, `EUR→INR = 95.0`, dated 2026-11) — clearly labeled as demo data, replaced by a rates API later.
- **Example:** `INV-9201` bills Hex Bolt in **EUR** against PO-1003 in **USD** → currency mismatch; `INV-9301` applies 18% GST to export freight that contract C-004 marks exempt → **₹2,700.00 tax at risk**.
- **FP guards:** only compare currency when vendor default currency or PO currency exists; never flag zero-tax lines unless contract explicitly sets `tax_pct=0` **and** item matches.

## R5 — Cancelled-service leakage

- **Intent:** recurring charges for cancelled software, terminated contracts, returned goods, services never delivered.
- **Logic:**
  ```
  join invoice line → contract line on (vendor_id, normalized item)
  if contract.status = 'cancelled' and invoice_date > contract.end_date:
      emit; amount_at_risk = line_total
  if po.status = 'cancelled' and invoice references that po: emit
  ```
- **Severity:** `critical` if paid (recovery task), `high` if unpaid.
- **Example:** `INV-9250` — CloudSuite monthly ₹29,500.00 (paid 2026-10-10) from NimbusCloud whose contract C-005 was **cancelled effective 2026-09-30** → recovery candidate.
- **FP guards:** require item-level match with a cancelled contract line; one-off items (no recurrence pattern) get `medium` instead of `critical`.

---

## Finding JSON shape (what Gemini's explanation stage receives)

```json
{
  "rule_id": "R1",
  "title": "Possible duplicate payment",
  "severity": "critical",
  "amount_at_risk": 4956.00,
  "currency": "INR",
  "confidence": 0.93,
  "entity_refs": {"invoice_numbers": ["INV-8821", "INV-8821-R2"], "payment_ids": ["PAY-5001", "PAY-5002"], "po_id": "PO-1001"},
  "evidence": [
    {"source": "invoices", "record_id": "INV-8821",    "field": "line_total", "value": "4956.00 INR"},
    {"source": "invoices", "record_id": "INV-8821-R2", "field": "line_total", "value": "4956.00 INR"},
    {"source": "payments", "record_id": "PAY-5002",    "field": "payment_date", "value": "2026-10-22"}
  ],
  "summary": "Same vendor + same amount + near-identical line items, 2-day gap, no credit note."
}
```

**Golden rule:** the rule engine computes *all* numbers above. Gemini only translates `summary + evidence` into finance language — it cannot add, remove, or re-estimate amounts.
