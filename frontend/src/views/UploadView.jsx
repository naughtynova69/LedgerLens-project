import React, { useState, useRef } from "react";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Database,
  Play,
  Layers,
  ArrowRight,
  RefreshCw,
  FolderOpen,
} from "lucide-react";
import { formatNumber, formatDate } from "../utils/formatters";

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
      desc: "Supplier invoice lines with items, quantities, rates, and tax",
      sample: "invoices.csv / PDF",
      color: "border-emerald-500/30 hover:border-emerald-500/60 bg-emerald-950/10",
      accent: "text-emerald-400",
    },
    {
      id: "purchase_orders",
      title: "Purchase Orders",
      desc: "Authorized PO numbers, authorized lines, quantities, and delivery dates",
      sample: "purchase_orders.csv",
      color: "border-blue-500/30 hover:border-blue-500/60 bg-blue-950/10",
      accent: "text-blue-400",
    },
    {
      id: "contracts",
      title: "Vendor Contracts",
      desc: "Negotiated price master, validity dates, discounts, and payment terms",
      sample: "contracts.csv",
      color: "border-amber-500/30 hover:border-amber-500/60 bg-amber-950/10",
      accent: "text-amber-400",
    },
    {
      id: "payments",
      title: "Payment Ledger",
      desc: "Disbursed payment records, settled amounts, FX rates, and bank dates",
      sample: "payments.csv",
      color: "border-purple-500/30 hover:border-purple-500/60 bg-purple-950/10",
      accent: "text-purple-400",
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
          batchId: res.batch_id,
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
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <UploadCloud className="w-6 h-6 text-emerald-400" />
            <span>Document Ingestion & Spend Data Center</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Upload enterprise spending feeds (CSV/PDF) or run continuous automated audit on loaded ledgers
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onSeedDemo}
            disabled={loadingAction}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs sm:text-sm transition-all shadow-lg shadow-emerald-950/20 disabled:opacity-50"
          >
            <Database className="w-4 h-4" />
            <span>Load 5 Demo Sample Files</span>
          </button>

          <button
            onClick={onRunDetect}
            disabled={loadingAction}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs sm:text-sm border border-slate-700 transition-all disabled:opacity-50"
          >
            <Play className="w-4 h-4 text-cyan-400" />
            <span>Run All Rules (R1–R5)</span>
          </button>
        </div>
      </div>

      {/* 4 Multi-Kind Dropzones */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {documentTypes.map((doc) => {
          const status = uploadStatus[doc.id];
          return (
            <div
              key={doc.id}
              onClick={() => fileInputRefs[doc.id].current?.click()}
              className={`p-5 rounded-2xl border-2 border-dashed transition-all cursor-pointer group relative overflow-hidden backdrop-blur-sm ${doc.color}`}
            >
              <input
                type="file"
                ref={fileInputRefs[doc.id]}
                onChange={(e) => handleFileSelect(doc.id, e)}
                className="hidden"
                accept=".csv,.pdf"
              />

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-bold uppercase tracking-wider ${doc.accent}`}>
                    {doc.title}
                  </span>
                  <div className="p-2 rounded-xl bg-slate-900/80 text-slate-400 group-hover:text-white transition-colors">
                    <FolderOpen className="w-4 h-4" />
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed min-h-[3rem]">
                  {doc.desc}
                </p>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span>Format: CSV / PDF</span>
                  <span className="text-slate-500">{doc.sample}</span>
                </div>

                {/* Upload Status Feedback */}
                {status && (
                  <div className="mt-2 p-2 rounded-lg bg-slate-900/90 text-xs border border-slate-800 flex items-center justify-between">
                    <span className="truncate max-w-[120px] text-slate-300 font-mono">
                      {status.name}
                    </span>
                    {status.status === "uploading" && (
                      <span className="text-amber-400 animate-pulse font-medium">Ingesting...</span>
                    )}
                    {status.status === "success" && (
                      <span className="text-emerald-400 font-bold flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {status.rows} rows
                      </span>
                    )}
                    {status.status === "error" && (
                      <span className="text-rose-400 flex items-center gap-1" title={status.error}>
                        <AlertCircle className="w-3.5 h-3.5" /> Error
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Ingested Batches Queue */}
      <div className="bg-[#0D1424] border border-slate-800/80 rounded-2xl p-6 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-white tracking-tight">
              Ingested Document Batches
            </h2>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Total Batches: {batches?.length || 0}
          </span>
        </div>

        {(!batches || batches.length === 0) ? (
          <div className="p-8 text-center text-xs text-slate-400 bg-slate-900/40 rounded-xl border border-slate-800">
            No document batches ingested yet. Click "Load 5 Demo Sample Files" or select files above.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead className="bg-[#111A2E] text-slate-400 uppercase text-[10px] font-semibold">
                <tr>
                  <th className="py-3 px-4">Batch ID</th>
                  <th className="py-3 px-4">Kind / Feed</th>
                  <th className="py-3 px-4 text-right">Rows Detected</th>
                  <th className="py-3 px-4 text-center">Pipeline State</th>
                  <th className="py-3 px-4">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                {batches.map((b) => (
                  <tr key={b.batch_id} className="hover:bg-slate-800/30">
                    <td className="py-3 px-4 font-mono font-bold text-white">
                      {b.batch_id}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
                        {b.kind}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-semibold text-emerald-400">
                      {formatNumber(b.rows_detected)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          b.state === "detected"
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                        }`}
                      >
                        {b.state === "detected" ? "Detection Verified" : "Ready for Audit"}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400 font-mono text-xs">
                      {b.created_at}
                    </td>
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
