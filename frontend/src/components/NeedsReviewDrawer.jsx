import React, { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, X } from "lucide-react";

const NUMERIC_FIELDS = new Set(["quantity", "unit_price", "tax_pct", "line_total"]);

function normalizeRecords(records) {
  return (records || []).map((rec, idx) => ({
    ...rec,
    _rowKey: rec.id ?? rec.record_id ?? rec.line_id ?? `row-${idx}`,
    invoice_number: rec.invoice_number ?? "",
    item: rec.item ?? "",
    quantity: rec.quantity ?? "",
    unit_price: rec.unit_price ?? "",
    tax_pct: rec.tax_pct ?? "",
    line_total: rec.line_total ?? "",
  }));
}

export function NeedsReviewDrawer({
  isOpen,
  onClose,
  batch,
  records = [],
  onSaveAndRedetect,
  saving = false,
}) {
  const [drafts, setDrafts] = useState(() => normalizeRecords(records));

  useEffect(() => {
    if (isOpen) {
      setDrafts(normalizeRecords(records));
    }
  }, [isOpen, records]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !saving) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.body.style.overflow = "unset";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose, saving]);

  if (!isOpen) return null;

  const handleFieldChange = (rowKey, field, value) => {
    setDrafts((prev) =>
      prev.map((row) => (row._rowKey === rowKey ? { ...row, [field]: value } : row))
    );
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!onSaveAndRedetect) return;

    const payload = drafts.map(({ _rowKey, ...rest }) => {
      const cleaned = { ...rest };
      for (const field of NUMERIC_FIELDS) {
        const raw = cleaned[field];
        if (raw === "" || raw === null || raw === undefined) {
          cleaned[field] = null;
        } else {
          const parsed = Number(raw);
          cleaned[field] = Number.isNaN(parsed) ? raw : parsed;
        }
      }
      return cleaned;
    });

    onSaveAndRedetect(payload);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-label="Needs Review Quarantine Drawer"
    >
      <div
        className="fixed inset-0 bg-slate-900/40 transition-opacity"
        onClick={() => !saving && onClose()}
      />

      <div className="relative z-10 w-full max-w-4xl bg-white border-l border-slate-200 shadow-lg flex flex-col h-full">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-slate-200 bg-slate-50">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] leading-none font-medium bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A]">
                <AlertTriangle className="w-3 h-3 text-[#D97706]" />
                Needs Review
              </span>
              {batch?.batch_id && (
                <span className="font-mono text-xs text-slate-500 truncate">
                  {batch.batch_id}
                </span>
              )}
            </div>
            <h2 className="text-[15px] font-semibold text-slate-900 tracking-[-0.01em]">
              Quarantined Invoice Lines
            </h2>
            <p className="text-xs text-slate-500">
              Correct extracted or malformed fields below, then save to re-run deterministic 3-way match detection.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Close drawer"
            className="p-1.5 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-200/70 transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto p-5 space-y-3 bg-white">
            {drafts.length === 0 ? (
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-10 text-center">
                <CheckCircle2 className="w-6 h-6 text-[#047857] mx-auto mb-2" />
                <p className="text-[13px] font-semibold text-slate-900">
                  No quarantined lines require review
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  All records in this batch passed schema validation.
                </p>
              </div>
            ) : (
              drafts.map((row, index) => (
                <div
                  key={row._rowKey}
                  className="bg-white border border-slate-200 rounded-lg p-4 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-slate-900 tabular-nums">
                        Line #{index + 1}
                      </span>
                      {row.vendor_id && (
                        <span className="font-mono text-[11px] text-slate-500">
                          {row.vendor_id}
                        </span>
                      )}
                    </div>
                    {(row.reason || row.validation_error) && (
                      <span className="text-[11px] leading-none font-medium text-[#92400E] bg-[#FFFBEB] border border-[#FDE68A] rounded px-2 py-1">
                        {row.reason || row.validation_error}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    <label className="block space-y-1">
                      <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.06em]">
                        Invoice Number
                      </span>
                      <input
                        type="text"
                        value={row.invoice_number}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "invoice_number", e.target.value)
                        }
                        className="w-full h-8 px-2.5 text-xs font-mono text-slate-900 bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900"
                      />
                    </label>

                    <label className="block space-y-1 sm:col-span-2">
                      <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.06em]">
                        Item Description
                      </span>
                      <input
                        type="text"
                        value={row.item}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "item", e.target.value)
                        }
                        className="w-full h-8 px-2.5 text-xs text-slate-900 bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.06em]">
                        Quantity
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={row.quantity}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "quantity", e.target.value)
                        }
                        className="w-full h-8 px-2.5 text-xs font-mono tabular-nums text-right text-slate-900 bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.06em]">
                        Unit Price
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={row.unit_price}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "unit_price", e.target.value)
                        }
                        className="w-full h-8 px-2.5 text-xs font-mono tabular-nums text-right text-slate-900 bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.06em]">
                        Tax %
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={row.tax_pct}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "tax_pct", e.target.value)
                        }
                        className="w-full h-8 px-2.5 text-xs font-mono tabular-nums text-right text-slate-900 bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.06em]">
                        Line Total
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={row.line_total}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "line_total", e.target.value)
                        }
                        className="w-full h-8 px-2.5 text-xs font-mono tabular-nums text-right text-slate-900 bg-white border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-slate-900"
                      />
                    </label>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-5 py-3.5 border-t border-slate-200 bg-slate-50 flex items-center justify-between gap-3">
            <span className="text-xs font-mono tabular-nums text-slate-500">
              {drafts.length} {drafts.length === 1 ? "line" : "lines"} queued
            </span>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={saving}
                className="h-8 px-3 text-xs font-medium rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving || drafts.length === 0}
                className="inline-flex items-center gap-1.5 h-8 px-3.5 text-xs font-medium rounded-md bg-slate-900 hover:bg-slate-800 text-white transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${saving ? "animate-spin" : ""}`} />
                {saving ? "Saving & Re-Running..." : "Save & Re-Run Detection"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
