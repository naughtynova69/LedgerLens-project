import React from "react";

export function StatCard({
  title,
  value,
  subtext,
  variant = "default",
}) {
  const valueColors = {
    default: "text-[#111827]",
    critical: "text-[#B91C1C]",
    emerald: "text-[#047857]",
  };

  const valueClass = valueColors[variant] || valueColors.default;

  return (
    <div className="p-4 rounded-lg bg-white border border-gray-200">
      <p className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
        {title}
      </p>
      <div
        className={`text-xl font-semibold font-mono tabular-nums tracking-tight mt-1.5 ${valueClass}`}
      >
        {value}
      </div>
      {subtext && (
        <p className="mt-1.5 text-xs text-gray-500">{subtext}</p>
      )}
    </div>
  );
}
