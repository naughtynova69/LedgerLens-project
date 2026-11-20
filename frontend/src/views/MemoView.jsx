import React, { useState } from "react";
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
    <div className="space-y-5">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <p className="text-xs text-[#6B7280]">
            Deterministic executive briefing grounded in R1–R5 proof trails
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {onRefreshMemo && (
            <button
              type="button"
              onClick={onRefreshMemo}
              className="px-3 py-1.5 rounded-lg bg-white hover:bg-gray-50 text-gray-700 font-medium text-xs border border-gray-200"
            >
              Refresh
            </button>
          )}

          <button
            type="button"
            onClick={handleCopy}
            className="px-3 py-1.5 rounded-lg bg-white hover:bg-gray-50 text-gray-700 font-medium text-xs border border-gray-200"
          >
            {copied ? "Copied" : "Copy Markdown"}
          </button>

          <button
            type="button"
            onClick={handleDownloadMd}
            className="px-3 py-1.5 rounded-lg bg-white hover:bg-gray-50 text-gray-700 font-medium text-xs border border-gray-200"
          >
            Download .md
          </button>

          <button
            type="button"
            onClick={() => window.print()}
            className="px-3 py-1.5 rounded-lg bg-[#111827] hover:bg-gray-800 text-white font-medium text-xs"
          >
            Print / PDF
          </button>
        </div>
      </div>

      {/* KPI Summary Strip */}
      <div className="bg-white border border-gray-200 rounded-lg grid grid-cols-2 sm:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-gray-200">
        <div className="p-3.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            Spend Audited
          </div>
          <div className="text-base font-semibold font-mono tabular-nums text-[#111827] mt-1">
            {formatCurrency(summary.total_spend_audited ?? 0)}
          </div>
        </div>
        <div className="p-3.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            Money at Risk
          </div>
          <div className="text-base font-semibold font-mono tabular-nums text-[#B91C1C] mt-1">
            {formatCurrency(summary.total_money_at_risk ?? 0)}
          </div>
        </div>
        <div className="p-3.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            Open Risk
          </div>
          <div className="text-base font-semibold font-mono tabular-nums text-[#111827] mt-1">
            {formatCurrency(summary.open_at_risk ?? 0)}
          </div>
        </div>
        <div className="p-3.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            Recovered
          </div>
          <div className="text-base font-semibold font-mono tabular-nums text-[#047857] mt-1">
            {formatCurrency(summary.recovered_amount ?? 0)}
          </div>
        </div>
      </div>

      {/* Breakdown by Rule */}
      {Object.keys(byRule).length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {Object.entries(byRule)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([rid, info]) => (
              <div key={rid} className="p-3 rounded-lg bg-[#FAFAFA] border border-gray-200 text-xs">
                <div className="font-mono font-medium text-[#111827]">{rid}</div>
                <div className="text-[#6B7280] text-[11px] mt-0.5">{info.count} finding(s)</div>
                <div className="font-mono tabular-nums font-medium text-[#B91C1C] mt-1">
                  {formatCurrency(info.amount_at_risk, info.currencies?.[0] || "INR")}
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Markdown Body */}
      <pre className="whitespace-pre-wrap font-mono text-xs text-[#111827] bg-[#FAFAFA] p-4 rounded-lg border border-gray-200 leading-relaxed overflow-x-auto">
        {memoText || "No audit findings available yet. Load the demo dataset or upload documents."}
      </pre>
    </div>
  );
}
