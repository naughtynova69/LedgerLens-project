import React, { useState, useRef } from "react";
import {
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  Database,
  Play,
  Layers,
  FolderOpen,
} from "lucide-react";
import { formatNumber } from "../utils/formatters";

export function UploadView({
  batches,
  onUploadFile,
  onSeedDemo,
  onRunDetect,
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
      desc: "Supplier invoice lines (CSV or PDF scan via Gemini 4 Carbon)",
      sample: "invoices.csv / .pdf",
      accent: "text-[#DC2626] bg-[#FEF2F2] border-[#FECACA]",
    },
    {
      id: "purchase_orders",
      title: "Purchase Orders",
      desc: "Authorized PO quantities, unit prices, and delivery windows",
      sample: "purchase_orders.csv / .pdf",
      accent: "text-[#D97706] bg-[#FFFBEB] border-[#FDE68A]",
    },
    {
      id: "contracts",
      title: "Vendor Contracts",
      desc: "Negotiated rates, agreed discounts, tax exemptions & end dates",
      sample: "contracts.csv / .pdf",
      accent: "text-[#059669] bg-[#ECFDF5] border-[#A7F3D0]",
    },
    {
      id: "payments",
      title: "Payment Ledger",
      desc: "Settled disbursements, FX rates to INR & settlement dates",
      sample: "payments.csv",
      accent: "text-[#4F46E5] bg-[#EEF2FF] border-[#C7D2FE]",
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
          rows: res.rows_detected,
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
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <UploadCloud className="w-5 h-5 text-[#059669]" />
            <span>Ingested Batches & Feed Center</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            Upload CSV/PDF documents or trigger Gemini extraction and deterministic R1–R5 audit checks
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={onSeedDemo}
            disabled={loadingAction}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#059669] hover:bg-[#047857] text-white font-semibold text-xs disabled:opacity-50"
          >
            <Database className="w-4 h-4" />
            <span>Load Demo Dataset</span>
          </button>

          <button
            onClick={onRunDetect}
            disabled={loadingAction}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs disabled:opacity-50"
          >
            <Play className="w-4 h-4 text-emerald-400" />
            <span>Run Rules (R1–R5)</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {documentTypes.map((doc) => {
          const status = uploadStatus[doc.id];
          return (
            <div
              key={doc.id}
              onClick={() => fileInputRefs[doc.id].current?.click()}
              className="p-5 rounded-xl border border-dashed border-slate-300 hover:border-slate-500 bg-white cursor-pointer transition-colors shadow-sm space-y-3"
            >
              <input
                type="file"
                ref={fileInputRefs[doc.id]}
                onChange={(e) => handleFileSelect(doc.id, e)}
                className="hidden"
                accept=".csv,.pdf,.png,.jpg,.jpeg"
              />

              <div className="flex items-center justify-between">
                <span className={`px-2 py-0.5 rounded-md text-[11px] font-bold uppercase border ${doc.accent}`}>
                  {doc.title}
                </span>
                <FolderOpen className="w-4 h-4 text-slate-400" />
              </div>

              <p className="text-xs text-slate-600 leading-relaxed min-h-[2.5rem]">{doc.desc}</p>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] font-mono text-slate-500">
                <span>CSV / PDF</span>
                <span>{doc.sample}</span>
              </div>

              {status && (
                <div className="p-2 rounded-lg bg-slate-50 border border-slate-200 text-xs flex items-center justify-between">
                  <span className="truncate max-w-[120px] font-mono text-slate-700">{status.name}</span>
                  {status.status === "uploading" && <span className="text-[#D97706]">Running...</span>}
                  {status.status === "success" && (
                    <span className="text-[#059669] font-semibold inline-flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {status.rows} rows
                    </span>
                  )}
                  {status.status === "error" && (
                    <span className="text-[#DC2626] inline-flex items-center gap-1" title={status.error}>
                      <AlertCircle className="w-3.5 h-3.5" /> Error
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Batches Table */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#059669]" />
            <h2 className="text-base font-bold text-slate-900">Ingested Document Batches</h2>
          </div>
          <span className="text-xs font-mono tabular-nums text-slate-500">
            Total: {batches?.length || 0}
          </span>
        </div>

        {!batches || batches.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500 bg-slate-50 rounded-xl border border-slate-200">
            No batches ingested yet.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[10px] font-bold">
                <tr>
                  <th className="py-2.5 px-4">Batch ID</th>
                  <th className="py-2.5 px-4">Feed</th>
                  <th className="py-2.5 px-4 text-right">Rows</th>
                  <th className="py-2.5 px-4 text-center">State</th>
                  <th className="py-2.5 px-4">Created At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {batches.map((b) => (
                  <tr key={b.batch_id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 font-mono font-bold text-slate-900">{b.batch_id}</td>
                    <td className="py-2.5 px-4 font-mono text-xs text-slate-700">{b.kind}</td>
                    <td className="py-2.5 px-4 text-right font-mono tabular-nums font-semibold text-[#059669]">
                      {formatNumber(b.rows_detected)}
                    </td>
                    <td className="py-2.5 px-4 text-center">
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]">
                        {b.state}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-mono text-xs text-slate-500">{b.created_at}</td>
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
