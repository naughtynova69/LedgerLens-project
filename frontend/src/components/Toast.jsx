import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";

export function Toast({ toast, onClose }) {
  if (!toast) return null;

  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-[#059669] shrink-0" />,
    warning: <AlertTriangle className="w-5 h-5 text-[#D97706] shrink-0" />,
    error: <XCircle className="w-5 h-5 text-[#DC2626] shrink-0" />,
    info: <Info className="w-5 h-5 text-[#4F46E5] shrink-0" />,
  };

  const borders = {
    success: "border-[#A7F3D0] bg-[#ECFDF5]",
    warning: "border-[#FDE68A] bg-[#FFFBEB]",
    error: "border-[#FECACA] bg-[#FEF2F2]",
    info: "border-[#C7D2FE] bg-[#EEF2FF]",
  };

  const type = toast.type || "info";

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg transition-all duration-300 max-w-md ${
        borders[type]
      }`}
    >
      {icons[type]}
      <div className="text-sm">
        {toast.title && <p className="font-semibold text-slate-900">{toast.title}</p>}
        <p className="text-slate-700 text-xs sm:text-sm">{toast.message}</p>
      </div>
      <button
        onClick={onClose}
        aria-label="Dismiss notification"
        className="ml-2 text-slate-500 hover:text-slate-800 transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
