import React from "react";
import {
  BookOpen,
  CheckCircle2,
  Code2,
  Cpu,
  Layers,
  Scale,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { RuleBadge } from "../components/RuleBadge";

export function RulesView() {
  const rules = [
    {
      id: "R1",
      name: "Duplicate & Near-Duplicate Invoices",
      intent: "Detects identical or slightly altered invoices submitted multiple times.",
      logic: `group invoices by vendor_id
for pair (A, B) with A.invoice_number != B.invoice_number:
  amount_match = |total_A - total_B| / total_A <= 0.005
  line_similarity = jaccard(items_A, items_B) >= 0.8
  num_similarity  = SequenceMatcher(num_A, num_B).ratio() >= 0.6
  date_gap        = |date_A - date_B| <= 30 days
  if amount_match and line_similarity and (num_similarity or date_gap):
    fire Finding (severity: critical if both paid, else high)`,
      severity: "Critical if paid twice (recovery); High if unpaid (block)",
      sampleAnomaly: "INV-8821 vs INV-8821-R2 · Sunbeam Electricals · ₹4,956.00 paid twice",
    },
    {
      id: "R2",
      name: "Contract Price Leakage",
      intent: "Catches unit price charges above negotiated contract rates. The contract always governs.",
      logic: `join invoice_line -> contract_line on (vendor_id, normalized_item)
where contract.status = 'active' and contract covers invoice_date
if invoice.unit_price > contract.contracted_unit_price:
  delta = invoice.unit_price - contract.contracted_unit_price
  amount_at_risk = delta * invoice.quantity * (1 + tax_pct/100)
  fire Finding (severity: high if unpaid, critical if paid)`,
      severity: "High if unpaid; Critical if paid",
      sampleAnomaly: "INV-9102 · LED Panel billed @ ₹465.00 vs contract C-001 @ ₹420.00 · ₹318.60 at risk",
    },
    {
      id: "R3",
      name: "Purchase Order Overbilling",
      intent: "Billed quantities exceeding authorized PO limit across cumulative shipments.",
      logic: `sum(invoice.quantity) per (po_id, normalized_item) across non-duplicate invoices
if total_billed_quantity > po.quantity:
  excess = total_billed_quantity - po.quantity
  amount_at_risk = excess * po.unit_price * (1 + tax_pct/100)
  fire Finding (severity: high)`,
      severity: "High",
      sampleAnomaly: "INV-9155 · Billed 60 × A4 Paper vs PO-1008 quantity 50 · ₹2,832.00 at risk",
    },
    {
      id: "R4",
      name: "Currency & Tax Errors",
      intent: "Flags currency mismatches against POs and unauthorized GST charged on exempt services.",
      logic: `1. Currency mismatch:
   if invoice.currency != po.currency:
     fire Finding(exposure = line_total, severity = high)
2. Tax error against contract:
   if invoice.tax_pct > contract.tax_pct:
     tax_delta = invoice.tax_pct - contract.tax_pct
     amount_at_risk = quantity * unit_price * (tax_delta / 100)
     fire Finding(severity = high)`,
      severity: "High",
      sampleAnomaly: "INV-9201 in EUR vs PO-1003 in USD (€225.00) · INV-9301 applied 18% GST on exempt freight (₹2,700.00)",
    },
    {
      id: "R5",
      name: "Cancelled-Service Leakage",
      intent: "Recurring charges billed after subscription termination or contract cancellation.",
      logic: `join invoice_line -> contract_line on (vendor_id, normalized_item)
if contract.status = 'cancelled' and invoice.invoice_date > contract.end_date:
  amount_at_risk = invoice.line_total
  fire Finding (severity: critical if paid, high if unpaid)`,
      severity: "Critical if paid (clawback task); High if unpaid",
      sampleAnomaly: "INV-9250 · CloudSuite monthly ₹29,500.00 billed 2026-10-08 after C-005 cancelled 2026-09-30",
    },
  ];

  return (
    <div className="space-y-8 animate-fadeIn max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
          <BookOpen className="w-6 h-6 text-emerald-400" />
          <span>Detection Engine & Rule Architecture</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Why LedgerLens is defensible: deterministic rule math decides; LLMs never hallucinate numbers
        </p>
      </div>

      {/* Core Architectural Moat */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-[#0C1222] via-[#0E1A2E] to-[#0A1728] border border-slate-800 space-y-4">
        <div className="flex items-center gap-2 text-xs font-bold text-emerald-400 uppercase tracking-wider">
          <Scale className="w-4 h-4" />
          Architectural Contract: The AI Explains, The Rules Engine Decides
        </div>
        <p className="text-sm text-slate-300 leading-relaxed">
          In corporate accounts payable, finance leadership will never approve clawbacks or payment blocks
          based on a black-box prompt saying <em>"this looks suspicious."</em>
          Every LedgerLens finding is mathematically proven by deterministic rules with citation chips
          (<code className="text-emerald-400 font-mono">EvidenceRef</code>), while Gemini crafts CFO-ready narratives.
        </p>
      </div>

      {/* 5 Rules Breakdown */}
      <div className="space-y-6">
        {rules.map((rule) => (
          <div
            key={rule.id}
            className="p-6 rounded-2xl bg-[#0D1424] border border-slate-800/80 space-y-4 shadow-xl"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                <RuleBadge ruleId={rule.id} full className="text-sm py-1 px-3" />
                <h3 className="text-base font-bold text-white">{rule.name}</h3>
              </div>
              <span className="text-xs font-mono text-slate-400 bg-slate-900 px-3 py-1 rounded-full border border-slate-800">
                Default Severity: {rule.severity}
              </span>
            </div>

            <p className="text-xs sm:text-sm text-slate-300">{rule.intent}</p>

            <div className="space-y-1.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Code2 className="w-3.5 h-3.5 text-cyan-400" />
                Deterministic Verification Pseudocode:
              </span>
              <pre className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 font-mono text-xs text-emerald-300 overflow-x-auto leading-relaxed">
                {rule.logic}
              </pre>
            </div>

            <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-xs">
              <span className="text-slate-400">Planted Demo Anomaly:</span>
              <span className="font-mono text-amber-300 font-semibold">{rule.sampleAnomaly}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
