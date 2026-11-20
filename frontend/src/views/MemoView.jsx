import React, { useState } from "react";
import {
  FileCheck2,
  Copy,
  Printer,
  Check,
  Download,
  RefreshCw,
  ShieldCheck,
  Calendar,
} from "lucide-react";
import { formatCurrency } from "../utils/formatters";

export function MemoView({ memoData, onRefreshMemo, onCopy }) {
  const [copied, setCopied] = useState(false);

  const memoText = memoData?.memo_markdown || "";
  const summary = memoData?.summary || {};
  const byRule = memoData?.by_rule || {};

  const handleCopy = () => {
    if (navigator.clipboard && memoText) {
      navigator.clipboard.writeText(memoText);
      setCopied(true);
      if (onCopy) onCopy();
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const handleDownloadMd = () => {
    const content = memoText || "# LedgerLens Audit Memo\n\nNo findings recorded yet.\n";
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ledgerlens-audit-memo-${new Date().toISOString().split("T")[0]}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <FileCheck2 className="w-6 h-6 text-[#059669]" />
            <span>CFO Audit Memo</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            One-click deterministic briefing grounded in line-level R1–R5 proof trails
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {onRefreshMemo && (
            <button
              onClick={onRefreshMemo}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs border border-slate-300"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Generate CFO Audit Memo</span>
            </button>
          )}

          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs border border-slate-300"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-[#059669]" />
                <span className="text-[#059669]">Copied Markdown</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-slate-500" />
                <span>Copy Markdown</span>
              </>
            )}
          </button>

          <button
            onClick={handleDownloadMd}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#059669] hover:bg-[#047857] text-white font-semibold text-xs shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download .md</span>
          </button>

          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Print / PDF</span>
          </button>
        </div>
      </div>

      {/* Structured KPI Summary Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-white border border-slate-200 shadow-sm">
          <div className="text-[11px] font-semibold uppercase text-slate-500">Spend Audited</div>
          <div className="text-lg font-bold font-mono tabular-nums text-slate-900 mt-1">
            {formatCurrency(summary.total_spend_audited ?? 0)}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-white border border-[#FECACA] shadow-sm">
          <div className="text-[11px] font-semibold uppercase text-slate-500">Money at Risk</div>
          <div className="text-lg font-bold font-mono tabular-nums text-[#DC2626] mt-1">
            {formatCurrency(summary.total_money_at_risk ?? 0)}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-white border border-[#FDE68A] shadow-sm">
          <div className="text-[11px] font-semibold uppercase text-slate-500">Open Risk</div>
          <div className="text-lg font-bold font-mono tabular-nums text-[#D97706] mt-1">
            {formatCurrency(summary.open_at_risk ?? 0)}
          </div>
        </div>
        <div className="p-4 rounded-xl bg-white border border-[#A7F3D0] shadow-sm">
          <div className="text-[11px] font-semibold uppercase text-slate-500">Recovered / Blocked</div>
          <div className="text-lg font-bold font-mono tabular-nums text-[#059669] mt-1">
            {formatCurrency(summary.recovered_amount ?? 0)}
          </div>
        </div>
      </div>

      {/* Printable Audit Memo Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 sm:p-10 shadow-sm space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#ECFDF5] border border-[#A7F3D0] flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-[#059669]" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">LedgerLens Executive Audit Memo</h2>
              <p className="text-xs text-slate-500">
                Deterministic Rule Math · Immutable Evidence Citations
              </p>
            </div>
          </div>

          <div className="text-right text-xs text-slate-500 font-mono space-y-0.5">
            <div className="inline-flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" />
              <span>{new Date().toISOString().split("T")[0]}</span>
            </div>
            <div className="text-[#059669] font-semibold">AUDIT-READY PROOF TRAIL</div>
          </div>
        </div>

        {Object.keys(byRule).length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
            {Object.entries(byRule)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([rid, info]) => (
                <div key={rid} className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs">
                  <div className="font-mono font-bold text-slate-900">{rid}</div>
                  <div className="text-slate-500">{info.count} finding(s)</div>
                  <div className="font-mono tabular-nums font-bold text-[#DC2626] mt-0.5">
                    {formatCurrency(info.amount_at_risk, info.currencies?.[0] || "INR")}
                  </div>
                </div>
              ))}
          </div>
        )}

        <pre className="whitespace-pre-wrap font-mono text-xs sm:text-sm text-slate-800 bg-slate-50 p-5 rounded-xl border border-slate-200 leading-relaxed overflow-x-auto">
          {memoText || "No audit findings available yet. Load the demo dataset or upload documents."}
        </pre>
      </div>
    </div>
  );
}
