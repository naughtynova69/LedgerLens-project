import React from "react";

export function SeverityBadge({ severity, className = "" }) {
  const sev = (severity || "low").toLowerCase();

  const config = {
    critical: {
      classes: "bg-red-50/80 text-red-700 border-red-200",
      dot: "bg-[#B91C1C]",
      label: "Critical",
    },
    high: {
      classes: "bg-gray-50 text-gray-700 border-gray-200",
      dot: "bg-gray-500",
      label: "High",
    },
    medium: {
      classes: "bg-gray-50 text-gray-600 border-gray-200",
      dot: "bg-gray-400",
      label: "Medium",
    },
    low: {
      classes: "bg-gray-50 text-gray-500 border-gray-200",
      dot: "bg-gray-400",
      label: "Low",
    },
  };

  const style = config[sev] || config.low;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium border whitespace-nowrap ${style.classes} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}
