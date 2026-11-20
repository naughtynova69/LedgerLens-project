import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";

export function Toast({ toast, onClose }) {
  if (!toast) return null;

  const icons = {
    success: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
    warning: <AlertTriangle className="w-5 h-5 text-amber-400" />,
    error: <XCircle className="w-5 h-5 text-rose-400" />,
    info: <Info className="w-5 h-5 text-sky-400" />,
  };

  const borders = {
    success: "border-emerald-500/30 bg-[#0E1E1C]",
    warning: "border-amber-500/30 bg-[#1F1B12]",
    error: "border-rose-500/30 bg-[#221217]",
    info: "border-sky-500/30 bg-[#0E1A2B]",
  };

  const type = toast.type || "info";

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl border shadow-xl backdrop-blur-md transition-all duration-300 ${
        borders[type]
      }`}
    >
      {icons[type]}
      <div className="text-sm">
        {toast.title && <p className="font-semibold text-white">{toast.title}</p>}
        <p className="text-slate-300">{toast.message}</p>
      </div>
      <button
        onClick={onClose}
        className="ml-2 text-slate-400 hover:text-white transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
