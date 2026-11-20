import React from "react";

const RULE_METADATA = {
  R1: {
    label: "Duplicate Invoice",
    short: "R1 Duplicate",
    tone: "bg-red-50/80 text-red-700 border-red-200/80",
  },
  R2: {
    label: "Contract Price Leakage",
    short: "R2 Price",
    tone: "bg-amber-50/80 text-amber-800 border-amber-200/80",
  },
  R3: {
    label: "PO Overbilling",
    short: "R3 PO",
    tone: "bg-amber-50/80 text-amber-800 border-amber-200/80",
  },
  R4: {
    label: "Currency / Tax Error",
    short: "R4 FX/Tax",
    tone: "bg-indigo-50/80 text-indigo-700 border-indigo-200/80",
  },
  R5: {
    label: "Cancelled Service",
    short: "R5 Cancelled",
    tone: "bg-red-50/80 text-red-700 border-red-200/80",
  },
  R6: {
    label: "Split-PO Bypass",
    short: "R6 Split-PO",
    tone: "bg-violet-50/80 text-violet-700 border-violet-200/80",
  },
  R7: {
    label: "GRN Mismatch",
    short: "R7 GRN",
    tone: "bg-sky-50/80 text-sky-700 border-sky-200/80",
  },
  R8: {
    label: "Cross-Entity Duplicate / Split-Invoice (Graph)",
    short: "R8 Graph-Dup",
    tone: "bg-red-50/80 text-red-700 border-red-200/80",
  },
  R9: {
    label: "Approver-Vendor Collusion (Graph)",
    short: "R9 Collusion",
    tone: "bg-purple-50/80 text-purple-700 border-purple-200/80",
  },
  R10: {
    label: "Contract Lineage & Unapplied Credits (Graph)",
    short: "R10 Lineage",
    tone: "bg-amber-50/80 text-amber-800 border-amber-200/80",
  },
};

export function RuleBadge({ ruleId, full = false, className = "" }) {
  const meta = RULE_METADATA[ruleId] || {
    label: ruleId,
    short: ruleId,
    tone: "bg-gray-50 text-gray-700 border-gray-200",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-mono font-medium border whitespace-nowrap ${meta.tone} ${className}`}
      title={meta.label}
    >
      {full ? `${ruleId} · ${meta.label}` : meta.short}
    </span>
  );
}
