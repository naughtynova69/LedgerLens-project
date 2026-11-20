import React from "react";

const RULE_METADATA = {
  R1: { label: "Duplicate Invoice", short: "R1 Duplicate", color: "text-rose-400 bg-rose-500/10 border-rose-500/20" },
  R2: { label: "Contract Price Leakage", short: "R2 Contract Price", color: "text-amber-400 bg-amber-500/10 border-amber-500/20" },
  R3: { label: "PO Overbilling", short: "R3 PO Mismatch", color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
  R4: { label: "Currency / Tax Error", short: "R4 Currency/Tax", color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20" },
  R5: { label: "Cancelled Service", short: "R5 Cancelled", color: "text-purple-400 bg-purple-500/10 border-purple-500/20" },
};

export function RuleBadge({ ruleId, full = false, className = "" }) {
  const meta = RULE_METADATA[ruleId] || {
    label: ruleId,
    short: ruleId,
    color: "text-slate-400 bg-slate-500/10 border-slate-500/20",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium border ${meta.color} ${className}`}
      title={meta.label}
    >
      {full ? `${ruleId} · ${meta.label}` : meta.short}
    </span>
  );
}
