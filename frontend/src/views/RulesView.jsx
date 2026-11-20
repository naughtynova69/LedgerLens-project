import React from "react";
import { BookOpen, Code2, Scale } from "lucide-react";
import { RuleBadge } from "../components/RuleBadge";

export function RulesView() {
  const rules = [
    {
      id: "R1",
      name: "Duplicate & Near-Duplicate Invoices",
      intent: "Detects the 61% non-identical duplicate problem via alphanumeric invoice canonicalization, date proximity, line-item Jaccard similarity, and same-PO double billing.",
      logic: `group invoices by vendor_id
for pair (A, B) with A.invoice_number != B.invoice_number:
  amount_ok = |total_A - total_B| / max(total_A, total_B) <= 0.005
  line_sim  = jaccard(items_A, items_B) >= 0.8
  num_sim   = max(SequenceMatcher(raw), SequenceMatcher(alnum_canonical)) >= 0.6
  date_gap  = |date_A - date_B| <= 30 days
  if amount_ok and line_sim and (num_sim or date_gap or same_po_item_qty):
    emit Finding (severity: critical if both paid else high, action: REQUEST_CREDIT_NOTE / HOLD_PAYMENT)`,
      severity: "Critical if paid twice; High if unpaid",
      sampleAnomaly: "INV-8821 vs INV-8821-R2 · Sunbeam Electricals · ₹4,956.00 paid twice",
    },
    {
      id: "R2",
      name: "Contract Price Leakage",
      intent: "Catches unit price charges above negotiated contract rates and missed agreed discounts. The contract always governs over the PO.",
      logic: `join invoice_line -> contract_line on (vendor_id, normalized_item)
where contract.status == 'active' and start_date <= invoice_date <= end_date
governed_rate = contracted_unit_price * (1 - discount_pct / 100)
if unit_price > contracted_unit_price or missed_discount:
  amount_at_risk = (billed_price - governed_rate) * quantity * (1 + tax_pct / 100)
  emit Finding (action: REQUEST_CREDIT_NOTE / DISPUTE_VENDOR)`,
      severity: "High if unpaid; Critical if paid",
      sampleAnomaly: "INV-9102 · LED Panel @ ₹465.00 vs C-001 @ ₹420.00 · ₹318.60 at risk",
    },
    {
      id: "R3",
      name: "Purchase Order Mismatch & Overbilling",
      intent: "Flags cumulative billed quantities above PO limits, premature billing before delivery on open POs, and unordered items billed against a PO.",
      logic: `sum(non_duplicate invoice.quantity) per (po_id, normalized_item)
if total_billed_qty > po.quantity:
  amount_at_risk = (total_billed_qty - po.quantity) * po.unit_price * (1 + tax_pct / 100)
if po.status not in ('delivered', 'received', 'closed') and invoice_date < po.expected_delivery:
  emit premature billing
if po_id in purchase_orders and item not on po_id:
  emit unordered item`,
      severity: "High (overbilling / unordered); Medium (premature)",
      sampleAnomaly: "INV-9155 · 60 × A4 Paper Box vs PO-1008 limit 50 · ₹2,832.00 at risk",
    },
    {
      id: "R4",
      name: "Currency, FX & Tax Errors",
      intent: "Flags currency mismatches (PO -> Contract -> Vendor), FX rate anomalies (>2% drift), tax applied on exempt contract items, and duplicate tax lines.",
      logic: `1. Currency mismatch vs PO / Contract / Vendor default_currency -> exposure = line_total
2. FX anomaly: |fx_rate_to_inr - REFERENCE_FX_RATES[currency]| / ref > 2% -> exposure = INR delta
3. Tax overcharge: invoice.tax_pct > contract.tax_pct -> exposure = qty * unit_price * tax_delta%
4. Duplicate tax lines on same (invoice_number, item)`,
      severity: "High",
      sampleAnomaly: "INV-9201 EUR vs PO-1003 USD (€225.00) · INV-9301 18% GST on exempt freight (₹2,700.00)",
    },
    {
      id: "R5",
      name: "Cancelled-Service Leakage",
      intent: "Catches charges billed after contract cancellation/termination/expiry, against inactive vendors, or referencing cancelled POs.",
      logic: `if contract.status in ('cancelled', 'terminated') or invoice_date > contract.end_date:
  emit Finding (amount_at_risk = line_total, action: CANCEL_AUTOPAY)
if vendor.status in ('cancelled', 'terminated', 'inactive') or po.status in ('cancelled', 'terminated'):
  emit Finding (action: CANCEL_AUTOPAY)`,
      severity: "Critical if paid; High if unpaid",
      sampleAnomaly: "INV-9250 · CloudSuite ₹29,500.00 billed 2026-10-08 after C-005 cancelled 2026-09-30",
    },
    {
      id: "R6",
      name: "Cross-Entity Duplicate & Threshold-Splitting (Graph)",
      intent: "Catches what tabular R1 cannot: two DIFFERENT vendor entities (sister firms, shell aliases) converging on the same bank account or tax identifier while billing near-identical invoices, plus approval-threshold splitting.",
      logic: `Cypher (LadybugDB, deterministic):
MATCH (i1:Invoice)-[:ISSUED_BY]->(v1:Vendor)-[:USES_BANK]->(b:BankAccount)
      <-[:USES_BANK]-(v2:Vendor)<-[:ISSUED_BY]-(i2:Invoice)
WHERE v1.vendor_id < v2.vendor_id
  AND amount_drift(i1, i2) <= 0.005
Python re-verification (pure stdlib):
  date_gap <= 30 days; amount_at_risk = min(grand_total_a, grand_total_b)
Splitting: approved invoices across vendors sharing bank/tax within 7 days,
each at 80-99.9% of the approver limit, combined sum > limit`,
      severity: "Critical if both paid; High otherwise",
      sampleAnomaly: "INV-9701 (V007) vs INV-9702 (V008) · shared HDFC ••••8841 · ₹12,000.00 at risk",
    },
    {
      id: "R7",
      name: "Approver-Vendor Collusion & Conflict of Interest (Graph)",
      intent: "Flags internal procurement fraud: an employee approves invoices for a vendor linked to them via shared personal infrastructure — bank account, registered address, or normalized phone.",
      logic: `Cypher (LadybugDB, deterministic):
MATCH (a:Approver)-[:APPROVED_INVOICE]->(i:Invoice)-[:ISSUED_BY]->
      (v:Vendor)-[:LOCATED_AT]->(addr:Address)<-[:APPROVER_LOCATED_AT]-(a)
-- plus shared-bank and shared-normalized-phone variants
emit Finding (severity: critical,
  action: HOLD_PAYMENT_AND_ESCALATE_INTERNAL_AUDIT)`,
      severity: "Critical",
      sampleAnomaly: "A-001 (Ravi Menon) approves INV-9801 (V009) · shared 12 MG Road address · ₹8,500.00",
    },
    {
      id: "R8",
      name: "Contract Lineage & Unapplied Credit Notes (Graph)",
      intent: "Traverses AMENDS contract lineage to catch invoices billed at a superseded rate after a signed amendment lowered it (ERP master-data lag), plus OPEN supplier credit notes while the vendor keeps billing.",
      logic: `Cypher (LadybugDB, deterministic):
MATCH (c_new:Contract)-[:AMENDS*1..5]->(c_old:Contract)<-[:GOVERNED_BY]-(i:Invoice)
WHERE c_new.unit_rate < c_old.unit_rate
Python re-verification: billed rate == superseded rate, invoice_date >=
amendment effective date; amount_at_risk = (old_rate - new_rate) * qty
Credits: OPEN credit note with vendor invoices dated >= issue_date`,
      severity: "High/Critical (lineage); Medium (credits)",
      sampleAnomaly: "INV-9601 @ ₹5,000 vs amended C-007 @ ₹4,500 (₹1,000.00) · CN-9001 OPEN ₹944.00",
    },
  ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-[#059669]" />
          <span>Deterministic Detection Engine (R1–R8)</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
          Zero LLM SDK calls inside `backend/app/detect/` — R1–R5 run pure tabular Python, R6–R8 run deterministic
          LadybugDB Cypher over the embedded knowledge graph. Every finding carries verifiable proof math.
        </p>
      </div>

      <div className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm space-y-2">
        <div className="flex items-center gap-2 text-xs font-bold text-[#059669] uppercase tracking-wider">
          <Scale className="w-4 h-4" />
          Neuro-Symbolic Contract: Gemini Extracts & Explains · Python Rules + Cypher Decide
        </div>
        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
          Finance controllers cannot freeze vendor payouts on an opaque score. Every finding below emits a
          deterministic <code className="font-mono text-slate-900 bg-slate-100 px-1 rounded">proof_trail</code> JSON
          payload linking the exact invoice line, contract clause, PO line, and payment record — and for R6–R8, the
          serialized multi-hop <code className="font-mono text-slate-900 bg-slate-100 px-1 rounded">proof_subgraph</code>{" "}
          from the embedded LadybugDB knowledge graph.
        </p>
      </div>

      <div className="space-y-4">
        {rules.map((rule) => (
          <div
            key={rule.id}
            className="p-5 rounded-xl bg-white border border-slate-200 shadow-sm space-y-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <RuleBadge ruleId={rule.id} full />
                <h3 className="text-sm sm:text-base font-bold text-slate-900">{rule.name}</h3>
              </div>
              <span className="text-xs font-mono text-slate-600 bg-slate-100 px-2.5 py-0.5 rounded-full border border-slate-200">
                {rule.severity}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-slate-600">{rule.intent}</p>

            <div className="space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 inline-flex items-center gap-1">
                <Code2 className="w-3.5 h-3.5 text-[#4F46E5]" />
                Deterministic Rule Logic
              </span>
              <pre className="p-3.5 rounded-lg bg-slate-900 text-emerald-300 font-mono text-xs overflow-x-auto leading-relaxed">
                {rule.logic}
              </pre>
            </div>

            <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="text-slate-500 font-semibold">Sample Dataset Verification:</span>
              <span className="font-mono text-slate-900">{rule.sampleAnomaly}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
