import React from "react";

export function StatCard({
  title,
  value,
  subtext,
  icon: Icon,
  variant = "default",
}) {
  const variantStyles = {
    default: {
      card: "bg-white border-slate-200",
      iconWrap: "bg-slate-100 text-slate-700 border-slate-200",
      valueText: "text-slate-900",
    },
    critical: {
      card: "bg-white border-[#FECACA]",
      iconWrap: "bg-[#FEF2F2] text-[#DC2626] border-[#FECACA]",
      valueText: "text-[#DC2626]",
    },
    amber: {
      card: "bg-white border-[#FDE68A]",
      iconWrap: "bg-[#FFFBEB] text-[#D97706] border-[#FDE68A]",
      valueText: "text-[#D97706]",
    },
    emerald: {
      card: "bg-white border-[#A7F3D0]",
      iconWrap: "bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]",
      valueText: "text-[#059669]",
    },
    indigo: {
      card: "bg-white border-[#C7D2FE]",
      iconWrap: "bg-[#EEF2FF] text-[#4F46E5] border-[#C7D2FE]",
      valueText: "text-[#4F46E5]",
    },
  };

  const style = variantStyles[variant] || variantStyles.default;

  return (
    <div
      className={`p-5 rounded-xl border shadow-sm transition-all duration-200 ${style.card}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {title}
          </p>
          <h3 className={`text-2xl sm:text-3xl font-bold font-mono tabular-nums tracking-tight mt-2 ${style.valueText}`}>
            {value}
          </h3>
        </div>
        {Icon && (
          <div className={`p-2.5 rounded-lg border shrink-0 ${style.iconWrap}`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      {subtext && (
        <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
          <span>{subtext}</span>
        </div>
      )}
    </div>
  );
}
