import React from "react";
import { AlertCircle, CheckCircle2, XCircle, RotateCcw } from "lucide-react";

export function StatusBadge({ status, className = "" }) {
  const st = (status || "open").toLowerCase();

  const config = {
    open: {
      bg: "bg-amber-500/10",
      text: "text-amber-400",
      border: "border-amber-500/30",
      label: "Needs Review",
      icon: AlertCircle,
    },
    approved: {
      bg: "bg-emerald-500/10",
      text: "text-emerald-400",
      border: "border-emerald-500/30",
      label: "Approved",
      icon: CheckCircle2,
    },
    rejected: {
      bg: "bg-rose-500/10",
      text: "text-rose-400",
      border: "border-rose-500/30",
      label: "Blocked / Rejected",
      icon: XCircle,
    },
    recovery: {
      bg: "bg-purple-500/10",
      text: "text-purple-400",
      border: "border-purple-500/30",
      label: "In Recovery",
      icon: RotateCcw,
    },
  };

  const style = config[st] || config.open;
  const Icon = style.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${style.bg} ${style.text} ${style.border} ${className}`}
    >
      <Icon className="w-3.5 h-3.5" />
      {style.label}
    </span>
  );
}
