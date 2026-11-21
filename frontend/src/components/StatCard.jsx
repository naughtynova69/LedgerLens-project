import React from "react";

export function StatCard({
  title,
  value,
  subtext,
  variant = "default",
}) {
  const valueColors = {
    default: "text-[var(--text-primary)]",
    critical: "text-[var(--risk-fg)]",
    emerald: "text-[var(--ok-fg)]",
    warn: "text-[var(--warn-fg)]",
  };

  const valueClass = valueColors[variant] || valueColors.default;

  return (
    <div className="p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-hairline)]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-muted)]">
        {title}
      </p>
      <div
        className={`text-[22px] leading-tight font-semibold font-mono tabular-nums tracking-tight mt-1 ${valueClass}`}
      >
        {value}
      </div>
      {subtext && (
        <p className="mt-1 text-xs text-[var(--text-secondary)]">{subtext}</p>
      )}
    </div>
  );
}
