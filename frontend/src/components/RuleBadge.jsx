import React from "react";

const RULE_METADATA = {
  R1: {
    label: "Duplicate Invoice",
    short: "R1 Duplicate",
  },
  R2: {
    label: "Contract Price Leakage",
    short: "R2 Price",
  },
  R3: {
    label: "PO Overbilling",
    short: "R3 PO",
  },
  R4: {
    label: "Currency / Tax Error",
    short: "R4 FX/Tax",
  },
  R5: {
    label: "Cancelled Service",
    short: "R5 Cancelled",
  },
  R8: {
    label: "Cross-Entity Duplicate / Split-Invoice (Graph)",
    short: "R8 Graph-Dup",
  },
  R9: {
    label: "Approver-Vendor Collusion (Graph)",
    short: "R9 Collusion",
  },
  R10: {
    label: "Contract Lineage & Unapplied Credits (Graph)",
    short: "R10 Lineage",
  },
  R6: {
    label: "Split-Invoice / PO Split Billing",
    short: "R6 Split-PO",
  },
  R7: {
    label: "GRN Mismatch",
    short: "R7 GRN",
  },
};

export function RuleBadge({ ruleId, full = false, className = "" }) {
  const meta = RULE_METADATA[ruleId] || {
    label: ruleId,
    short: ruleId,
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-mono font-medium bg-gray-50 text-gray-700 border border-gray-200 whitespace-nowrap ${className}`}
      title={meta.label}
    >
      {full ? `${ruleId} · ${meta.label}` : meta.short}
    </span>
  );
}
