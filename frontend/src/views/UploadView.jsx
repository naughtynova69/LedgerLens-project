import React, { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Database,
  FolderOpen,
  Layers,
  Loader2,
  Play,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { formatNumber } from "../utils/formatters";

export function UploadView({
  batches,
  onUploadFile,
  onSeedDemo,
  onRunDetect,
  onRunPayrunSweep,
  runningSweep = false,
  loadingAction,
}) {
  const [uploadStatus, setUploadStatus] = useState({});
  const fileInputRefs = {
    invoices: useRef(null),
    purchase_orders: useRef(null),
    contracts: useRef(null),
    payments: useRef(null),
  };

  const documentTypes = [
    {
      id: "invoices",
      title: "Invoices",
      desc: "Supplier invoice lines (CSV or PDF scan via Gemini Vision)",
      sample: "invoices.csv / .pdf",
      accent: "text-[#991B1B] bg-[#FEF2F2] border-[#FECACA]",
    },
    {
      id: "purchase_orders",
      title: "Purchase Orders",
      desc: "Authorized PO quantities, unit prices, and delivery windows",
      sample: "purchase_orders.csv / .pdf",
      accent: "text-[#92400E] bg-[#FFFBEB] border-[#FDE68A]",
    },
    {
      id: "contracts",
      title: "Vendor Contracts",
      desc: "Negotiated rates, agreed discounts, tax exemptions & end dates",
      sample: "contracts.csv / .pdf",
      accent: "text-[#065F46] bg-[#ECFDF5] border-[#A7F3D0]",
    },
    {
      id: "payments",
      title: "Payment Ledger",
      desc: "Settled disbursements, FX rates to INR & settlement dates",
      sample: "payments.csv",
      accent: "text-slate-700 bg-slate-100 border-[#E2E8F0]",
    },
  ];

  const handleFileSelect = async (kind, e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus((prev) => ({
      ...prev,
      [kind]: { status: "uploading", name: file.name },
    }));

    try {
      const res = await onUploadFile(kind, file);
      setUploadStatus((prev) => ({
        ...prev,
        [kind]: {
          status: "success",
          name: file.name,
          rows: res.rows_detected ?? res.rows_extracted ?? 0,
        },
      }));
    } catch (err) {
      setUploadStatus((prev) => ({
        ...prev,
        [kind]: { status: "error", name: file.name, error: err.message },
      }));
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg sm:text-xl font-semibold text-slate-900 tracking-tight flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-slate-700" aria-hidden="true" />
            <span>Ingested Batches &amp; Feed Center</span>
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Upload CSV or PDF documents for automated extraction, R1–R10 audit checks, and explanations.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {onRunPayrunSweep && (
            <button
              type="button"
              onClick={onRunPayrunSweep}
              disabled={runningSweep || loadingAction}
              className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs transition-colors disabled:opacity-50"
            >
              {runningSweep ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
              )}
              <span>{runningSweep ? "Sweeping…" : "Run Pay-Run Sweep"}</span>
            </button>
          )}

          <button
            type="button"
            onClick={onRunDetect}
            disabled={loadingAction}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[#E2E8F0] bg-white hover:bg-slate-50 text-slate-900 font-medium text-xs transition-colors disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5 text-[#047857]" aria-hidden="true" />
            <span>Run Rules (R1–R10)</span>
          </button>

          <button
            type="button"
            onClick={onSeedDemo}
            disabled={loadingAction}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-slate-100 text-slate-700 font-medium text-xs transition-colors disabled:opacity-50"
          >
            <Database className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
            <span>Seed Demo</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {documentTypes.map((doc) => {
          const status = uploadStatus[doc.id];
          return (
            <div key={doc.id} className="relative">
              <input
                type="file"
                ref={fileInputRefs[doc.id]}
                onChange={(e) => handleFileSelect(doc.id, e)}
                className="sr-only"
                aria-label={`Upload ${doc.title}`}
                accept=".csv,.pdf,.png,.jpg,.jpeg"
              />
              <button
                type="button"
                onClick={() => fileInputRefs[doc.id].current?.click()}
                className="w-full text-left p-4 rounded-md border border-dashed border-[#CBD5E1] hover:border-slate-500 bg-white transition-colors space-y-2.5"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase border ${doc.accent}`}
                  >
                    {doc.title}
                  </span>
                  <FolderOpen className="w-4 h-4 text-slate-400" aria-hidden="true" />
                </div>

                <p className="text-xs text-slate-600 leading-relaxed min-h-[2.5rem]">{doc.desc}</p>

                <div className="pt-2 border-t border-[#E2E8F0] flex items-center justify-between text-[11px] font-mono text-slate-500">
                  <span>CSV / PDF</span>
                  <span>{doc.sample}</span>
                </div>

                {status && (
                  <div className="p-2 rounded bg-[#F8FAFC] border border-[#E2E8F0] text-xs flex items-center justify-between">
                    <span className="truncate max-w-[120px] font-mono text-slate-700">
                      {status.name}
                    </span>
                    {status.status === "uploading" && (
                      <span className="text-[#92400E]">Running…</span>
                    )}
                    {status.status === "success" && (
                      <span className="text-[#065F46] font-semibold inline-flex items-center gap-1 tabular-nums">
                        <CheckCircle2 className="w-3.5 h-3.5" aria-hidden="true" />
                        {status.rows} rows
                      </span>
                    )}
                    {status.status === "error" && (
                      <span
                        className="text-[#991B1B] inline-flex items-center gap-1"
                        title={status.error}
                      >
                        <AlertCircle className="w-3.5 h-3.5" aria-hidden="true" /> Error
                      </span>
                    )}
                  </div>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Batches Table */}
      <div className="bg-white border border-[#E2E8F0] rounded-md p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-slate-700" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-slate-900">Ingested Document Batches</h2>
          </div>
          <span className="text-xs font-mono tabular-nums text-slate-500">
            Total: {batches?.length || 0}
          </span>
        </div>

        {!batches || batches.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 bg-[#F8FAFC] rounded-md border border-[#E2E8F0]">
            No batches ingested yet.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border border-[#E2E8F0]">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-slate-500 uppercase text-[10px] font-semibold">
                <tr>
                  <th className="py-2 px-3">Batch ID</th>
                  <th className="py-2 px-3">Feed</th>
                  <th className="py-2 px-3 text-right">Rows</th>
                  <th className="py-2 px-3 text-center">State</th>
                  <th className="py-2 px-3">Created At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {batches.map((b) => (
                  <tr key={b.batch_id} className="hover:bg-slate-50">
                    <td className="py-2 px-3 font-mono font-semibold text-slate-900">
                      {b.batch_id}
                    </td>
                    <td className="py-2 px-3 font-mono text-slate-700">{b.kind}</td>
                    <td className="py-2 px-3 text-right font-mono tabular-nums font-semibold text-[#065F46]">
                      {formatNumber(b.rows_detected)}
                    </td>
                    <td className="py-2 px-3 text-center">
                      <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0]">
                        {b.state}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-mono text-slate-500">{b.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
