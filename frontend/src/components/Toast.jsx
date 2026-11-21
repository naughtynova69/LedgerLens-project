import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";

export function Toast({ toast, onClose }) {
  if (!toast) return null;

  const icons = {
    success: <CheckCircle2 className="w-4 h-4 text-[var(--ok-dot)] shrink-0" />,
    warning: <AlertTriangle className="w-4 h-4 text-[var(--warn-dot)] shrink-0" />,
    error: <XCircle className="w-4 h-4 text-[var(--risk-dot)] shrink-0" />,
    info: <Info className="w-4 h-4 text-[var(--text-primary)] shrink-0" />,
  };

  const borders = {
    success: "border-[var(--ok-border)] bg-[var(--ok-bg)]",
    warning: "border-[var(--warn-border)] bg-[var(--warn-bg)]",
    error: "border-[var(--risk-border)] bg-[var(--risk-bg)]",
    info: "border-[var(--border-hairline)] bg-[var(--bg-surface)]",
  };

  const type = toast.type || "info";

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-5 right-5 z-50 flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg border shadow-sm transition-opacity duration-150 max-w-md ${
        borders[type] || borders.info
      }`}
    >
      {icons[type] || icons.info}
      <div className="text-[13px] leading-snug min-w-0">
        {toast.title && (
          <p className="font-semibold text-[var(--text-primary)]">{toast.title}</p>
        )}
        <p className="text-[var(--text-secondary)] text-xs">{toast.message}</p>
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="Dismiss notification"
        className="ml-2 p-0.5 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors duration-100"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
