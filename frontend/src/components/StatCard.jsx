import React from "react";

export function StatCard({
  title,
  value,
  subtext,
  icon: Icon,
  trend,
  trendPositive,
  highlight = false,
  variant = "default",
}) {
  const variantStyles = {
    default: "border-slate-800 bg-[#0F172A]/70 hover:border-slate-700",
    critical: "border-rose-900/40 bg-gradient-to-br from-[#1C101E] to-[#121324] hover:border-rose-800/60 shadow-lg shadow-rose-950/20",
    emerald: "border-emerald-900/40 bg-gradient-to-br from-[#0B1E19] to-[#0D1624] hover:border-emerald-800/60 shadow-lg shadow-emerald-950/20",
    blue: "border-sky-900/40 bg-gradient-to-br from-[#0F1A2E] to-[#0B1324] hover:border-sky-800/60 shadow-lg shadow-sky-950/20",
  };

  const cardStyle = variantStyles[variant] || variantStyles.default;

  return (
    <div
      className={`p-5 rounded-2xl border transition-all duration-300 relative overflow-hidden backdrop-blur-md ${cardStyle}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-400">
            {title}
          </p>
          <h3 className="text-2xl sm:text-3xl font-bold font-mono tracking-tight text-white mt-2">
            {value}
          </h3>
        </div>
        {Icon && (
          <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/50 text-slate-300">
            <Icon className="w-5 h-5 text-emerald-400" />
          </div>
        )}
      </div>

      {(subtext || trend) && (
        <div className="mt-4 flex items-center justify-between text-xs text-slate-400 pt-3 border-t border-slate-800/60">
          <span>{subtext}</span>
          {trend && (
            <span
              className={`font-medium ${
                trendPositive ? "text-emerald-400" : "text-amber-400"
              }`}
            >
              {trend}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
