import React from "react";
import { AlertCircle, CheckCircle2, XCircle, RotateCcw } from "lucide-react";

export function StatusBadge({ status, className = "" }) {
  const st = (status || "open").toLowerCase();

  const config = {
    open: {
      bg: "bg-[#FFFBEB]",
      text: "text-[#D97706]",
      border: "border-[#FDE68A]",
      label: "Open",
      icon: AlertCircle,
    },
    approved: {
      bg: "bg-[#ECFDF5]",
      text: "text-[#059669]",
      border: "border-[#A7F3D0]",
      label: "Approved",
      icon: CheckCircle2,
    },
    rejected: {
      bg: "bg-[#FEF2F2]",
      text: "text-[#DC2626]",
      border: "border-[#FECACA]",
      label: "Rejected",
      icon: XCircle,
    },
    recovery: {
      bg: "bg-[#ECFDF5]",
      text: "text-[#059669]",
      border: "border-[#A7F3D0]",
      label: "Recovered",
      icon: RotateCcw,
    },
    recover: {
      bg: "bg-[#ECFDF5]",
      text: "text-[#059669]",
      border: "border-[#A7F3D0]",
      label: "Recovered",
      icon: RotateCcw,
    },
    reject: {
      bg: "bg-[#FEF2F2]",
      text: "text-[#DC2626]",
      border: "border-[#FECACA]",
      label: "Rejected",
      icon: XCircle,
    },
    approve: {
      bg: "bg-[#ECFDF5]",
      text: "text-[#059669]",
      border: "border-[#A7F3D0]",
      label: "Approved",
      icon: CheckCircle2,
    },
  };

  const style = config[st] || config.open;
  const Icon = style.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold border whitespace-nowrap ${style.bg} ${style.text} ${style.border} ${className}`}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      {style.label}
    </span>
  );
}
