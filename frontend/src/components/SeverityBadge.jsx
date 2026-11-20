import React from "react";

export function SeverityBadge({ severity, className = "" }) {
  const sev = (severity || "low").toLowerCase();

  const config = {
    critical: {
      bg: "bg-[#FEF2F2]",
      text: "text-[#DC2626]",
      border: "border-[#FECACA]",
      dot: "bg-[#DC2626]",
      label: "CRITICAL",
    },
    high: {
      bg: "bg-[#FFFBEB]",
      text: "text-[#D97706]",
      border: "border-[#FDE68A]",
      dot: "bg-[#D97706]",
      label: "HIGH",
    },
    medium: {
      bg: "bg-[#EEF2FF]",
      text: "text-[#4F46E5]",
      border: "border-[#C7D2FE]",
      dot: "bg-[#4F46E5]",
      label: "MEDIUM",
    },
    low: {
      bg: "bg-slate-100",
      text: "text-slate-600",
      border: "border-slate-200",
      dot: "bg-slate-500",
      label: "LOW",
    },
  };

  const style = config[sev] || config.low;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide border whitespace-nowrap ${style.bg} ${style.text} ${style.border} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}
