import React from "react";

export function SeverityBadge({ severity, className = "" }) {
  const sev = (severity || "low").toLowerCase();

  const config = {
    critical: {
      bg: "bg-rose-500/10",
      text: "text-rose-400",
      border: "border-rose-500/30",
      dot: "bg-rose-500 animate-pulse",
      label: "CRITICAL",
    },
    high: {
      bg: "bg-amber-500/10",
      text: "text-amber-400",
      border: "border-amber-500/30",
      dot: "bg-amber-500",
      label: "HIGH",
    },
    medium: {
      bg: "bg-sky-500/10",
      text: "text-sky-400",
      border: "border-sky-500/30",
      dot: "bg-sky-500",
      label: "MEDIUM",
    },
    low: {
      bg: "bg-slate-500/10",
      text: "text-slate-400",
      border: "border-slate-500/30",
      dot: "bg-slate-500",
      label: "LOW",
    },
  };

  const style = config[sev] || config.low;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide border ${style.bg} ${style.text} ${style.border} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}
