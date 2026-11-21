import React from "react";

export function SeverityBadge({ severity, className = "" }) {
  const sev = (severity || "low").toLowerCase();

  const config = {
    critical: {
      classes:
        "bg-[var(--risk-bg)] text-[var(--risk-fg)] border-[var(--risk-border)]",
      dot: "bg-[var(--risk-dot)]",
      label: "Critical",
    },
    high: {
      classes:
        "bg-[var(--warn-bg)] text-[var(--warn-fg)] border-[var(--warn-border)]",
      dot: "bg-[var(--warn-dot)]",
      label: "High",
    },
    medium: {
      classes:
        "bg-[var(--neutral-bg)] text-[var(--neutral-fg)] border-[var(--neutral-border)]",
      dot: "bg-[#64748B]",
      label: "Medium",
    },
    low: {
      classes:
        "bg-[var(--neutral-bg)] text-[var(--text-muted)] border-[var(--neutral-border)]",
      dot: "bg-[#94A3B8]",
      label: "Low",
    },
  };

  const style = config[sev] || config.low;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded text-[11px] leading-none font-medium border whitespace-nowrap ${style.classes} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${style.dot}`} />
      {style.label}
    </span>
  );
}
