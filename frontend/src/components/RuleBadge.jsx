import React from "react";

const RULE_METADATA = {
  R1: {
    label: "Duplicate Invoice",
    short: "R1 Duplicate",
    color: "text-[#DC2626] bg-[#FEF2F2] border-[#FECACA]",
  },
  R2: {
    label: "Contract Price Leakage",
    short: "R2 Price",
    color: "text-[#D97706] bg-[#FFFBEB] border-[#FDE68A]",
  },
  R3: {
    label: "PO Overbilling",
    short: "R3 PO",
    color: "text-[#D97706] bg-[#FFFBEB] border-[#FDE68A]",
  },
  R4: {
    label: "Currency / Tax Error",
    short: "R4 FX/Tax",
    color: "text-[#4F46E5] bg-[#EEF2FF] border-[#C7D2FE]",
  },
  R5: {
    label: "Cancelled Service",
    short: "R5 Cancelled",
    color: "text-[#DC2626] bg-[#FEF2F2] border-[#FECACA]",
  },
};

export function RuleBadge({ ruleId, full = false, className = "" }) {
  const meta = RULE_METADATA[ruleId] || {
    label: ruleId,
    short: ruleId,
    color: "text-slate-700 bg-slate-100 border-slate-200",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono font-semibold border whitespace-nowrap ${meta.color} ${className}`}
      title={meta.label}
    >
      {full ? `${ruleId} · ${meta.label}` : meta.short}
    </span>
  );
}
