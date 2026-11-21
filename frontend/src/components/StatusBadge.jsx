import React from "react";

export function StatusBadge({ status, className = "" }) {
  const st = (status || "open").toLowerCase();

  const config = {
    open: {
      classes:
        "bg-[var(--neutral-bg)] text-[var(--neutral-fg)] border-[var(--neutral-border)]",
      label: "Open",
    },
    approved: {
      classes:
        "bg-[var(--ok-bg)] text-[var(--ok-fg)] border-[var(--ok-border)]",
      label: "Approved",
    },
    approve: {
      classes:
        "bg-[var(--ok-bg)] text-[var(--ok-fg)] border-[var(--ok-border)]",
      label: "Approved",
    },
    recovery: {
      classes:
        "bg-[var(--ok-bg)] text-[var(--ok-fg)] border-[var(--ok-border)]",
      label: "Recovered",
    },
    recover: {
      classes:
        "bg-[var(--ok-bg)] text-[var(--ok-fg)] border-[var(--ok-border)]",
      label: "Recovered",
    },
    rejected: {
      classes:
        "bg-[var(--risk-bg)] text-[var(--risk-fg)] border-[var(--risk-border)]",
      label: "Disputed",
    },
    reject: {
      classes:
        "bg-[var(--risk-bg)] text-[var(--risk-fg)] border-[var(--risk-border)]",
      label: "Disputed",
    },
    disputed: {
      classes:
        "bg-[var(--risk-bg)] text-[var(--risk-fg)] border-[var(--risk-border)]",
      label: "Disputed",
    },
  };

  const style = config[st] || config.open;

  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] leading-none font-medium border whitespace-nowrap ${style.classes} ${className}`}
    >
      {style.label}
    </span>
  );
}
