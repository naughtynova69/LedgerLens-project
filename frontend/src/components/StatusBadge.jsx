import React from "react";

export function StatusBadge({ status, className = "" }) {
  const st = (status || "open").toLowerCase();

  const config = {
    open: {
      classes: "bg-gray-50 text-gray-700 border-gray-200",
      label: "Open",
    },
    approved: {
      classes: "bg-emerald-50/80 text-emerald-700 border-emerald-200",
      label: "Approved",
    },
    approve: {
      classes: "bg-emerald-50/80 text-emerald-700 border-emerald-200",
      label: "Approved",
    },
    recovery: {
      classes: "bg-emerald-50/80 text-emerald-700 border-emerald-200",
      label: "Recovered",
    },
    recover: {
      classes: "bg-emerald-50/80 text-emerald-700 border-emerald-200",
      label: "Recovered",
    },
    rejected: {
      classes: "bg-red-50/80 text-red-700 border-red-200",
      label: "Disputed",
    },
    reject: {
      classes: "bg-red-50/80 text-red-700 border-red-200",
      label: "Disputed",
    },
  };

  const style = config[st] || config.open;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium border whitespace-nowrap ${style.classes} ${className}`}
    >
      {style.label}
    </span>
  );
}
