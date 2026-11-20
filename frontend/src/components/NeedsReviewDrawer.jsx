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
        className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity"
        onClick={() => !saving && onClose()}
      />

      <div className="relative z-10 w-full max-w-4xl bg-white border-l border-gray-200 shadow-2xl flex flex-col h-full">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-6 py-4 border-b border-gray-200 bg-slate-50">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200">
                <AlertTriangle className="w-3 h-3" />
                Needs Review
              </span>
              {batch?.batch_id && (
                <span className="font-mono text-xs text-[#6B7280] truncate">
                  {batch.batch_id}
                </span>
              )}
            </div>
            <h2 className="text-base font-semibold text-[#111827] tracking-tight">
              Quarantined Invoice Lines
            </h2>
            <p className="text-xs text-[#6B7280]">
              Correct extracted or malformed fields below, then save to re-run deterministic 3-way match detection.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Close drawer"
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-200/70 transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {drafts.length === 0 ? (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-10 text-center">
                <CheckCircle2 className="w-7 h-7 text-[#047857] mx-auto mb-2" />
                <p className="text-sm font-medium text-[#111827]">
                  No quarantined lines require review
                </p>
                <p className="text-xs text-[#6B7280] mt-1">
                  All records in this batch passed schema validation.
                </p>
              </div>
            ) : (
              drafts.map((row, index) => (
                <div
                  key={row._rowKey}
                  className="bg-white border border-gray-200 rounded-lg p-4 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-[#111827]">
                        Line #{index + 1}
                      </span>
                      {row.vendor_id && (
                        <span className="font-mono text-[11px] text-[#6B7280]">
                          {row.vendor_id}
                        </span>
                      )}
                    </div>
                    {(row.reason || row.validation_error) && (
                      <span className="text-[11px] font-medium text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-0.5">
                        {row.reason || row.validation_error}
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    <label className="block space-y-1">
                      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-wider">
                        Invoice Number
                      </span>
                      <input
                        type="text"
                        value={row.invoice_number}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "invoice_number", e.target.value)
                        }
                        className="w-full px-2.5 py-1.5 text-xs font-mono text-[#111827] bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900/15 focus:border-slate-500"
                      />
                    </label>

                    <label className="block space-y-1 sm:col-span-2">
                      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-wider">
                        Item Description
                      </span>
                      <input
                        type="text"
                        value={row.item}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "item", e.target.value)
                        }
                        className="w-full px-2.5 py-1.5 text-xs text-[#111827] bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900/15 focus:border-slate-500"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-wider">
                        Quantity
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={row.quantity}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "quantity", e.target.value)
                        }
                        className="w-full px-2.5 py-1.5 text-xs font-mono tabular-nums text-[#111827] bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900/15 focus:border-slate-500"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-wider">
                        Unit Price
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={row.unit_price}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "unit_price", e.target.value)
                        }
                        className="w-full px-2.5 py-1.5 text-xs font-mono tabular-nums text-[#111827] bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900/15 focus:border-slate-500"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-wider">
                        Tax %
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={row.tax_pct}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "tax_pct", e.target.value)
                        }
                        className="w-full px-2.5 py-1.5 text-xs font-mono tabular-nums text-[#111827] bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900/15 focus:border-slate-500"
                      />
                    </label>

                    <label className="block space-y-1">
                      <span className="text-[11px] font-medium text-[#6B7280] uppercase tracking-wider">
                        Line Total
                      </span>
                      <input
                        type="number"
                        step="any"
                        value={row.line_total}
                        onChange={(e) =>
                          handleFieldChange(row._rowKey, "line_total", e.target.value)
                        }
                        className="w-full px-2.5 py-1.5 text-xs font-mono tabular-nums text-[#111827] bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900/15 focus:border-slate-500"
                      />
                    </label>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-gray-200 bg-slate-50 flex items-center justify-between gap-3">
            <span className="text-xs font-mono tabular-nums text-[#6B7280]">
              {drafts.length} {drafts.length === 1 ? "line" : "lines"} queued
            </span>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                disabled={saving}
                className="px-3 py-2 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving || drafts.length === 0}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium rounded-lg bg-[#111827] hover:bg-gray-800 text-white transition-colors disabled:opacity-50"
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
