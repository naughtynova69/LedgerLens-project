import React, { useState } from "react";
import {
  FileCheck2,
  Copy,
  Printer,
  Check,
  Download,
  ShieldCheck,
  Building2,
  Calendar,
} from "lucide-react";

export function MemoView({ memoText, stats, onCopy }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (navigator.clipboard && memoText) {
      navigator.clipboard.writeText(memoText);
      setCopied(true);
      if (onCopy) onCopy();
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-fadeIn">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <FileCheck2 className="w-6 h-6 text-emerald-400" />
            <span>Executive Audit Memo</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Automated one-click briefing ready for CFO, Audit Committee, and Procurement
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-semibold text-xs transition-all border border-slate-700"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 text-emerald-400" />
                <span className="text-emerald-400">Copied to Clipboard!</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4 text-slate-300" />
                <span>Copy Markdown</span>
              </>
            )}
          </button>

          <button
            onClick={handlePrint}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs transition-all shadow-md shadow-emerald-950/20"
          >
            <Printer className="w-4 h-4" />
            <span>Print / Export PDF</span>
          </button>
        </div>
      </div>

      {/* Styled Printable Memo Document */}
      <div className="bg-[#0B101D] border border-slate-800 rounded-3xl p-8 sm:p-12 shadow-2xl relative overflow-hidden text-slate-200">
        {/* Top Watermark / Seal */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-6 mb-8">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <ShieldCheck className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold font-mono tracking-tight text-white">
                Ledger<span className="text-emerald-400">Lens</span> Audit Memo
              </h2>
              <p className="text-xs text-slate-400">
                Official Spend Leakage & Recovery Assessment
              </p>
            </div>
          </div>

          <div className="text-right text-xs text-slate-400 space-y-1">
            <div className="flex items-center justify-end gap-1.5 font-mono">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              <span>{new Date().toISOString().split("T")[0]}</span>
            </div>
            <div className="font-mono text-emerald-400 font-semibold">
              CLASSIFICATION: CONFIDENTIAL
            </div>
          </div>
        </div>

        {/* Rendered Memo Body */}
        <div className="prose prose-invert max-w-none space-y-6 text-sm leading-relaxed">
          <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-2xl">
            <h3 className="text-sm font-bold uppercase tracking-wider text-emerald-400 mb-2">
              Executive Briefing Summary
            </h3>
            <p className="text-slate-300">
              This deterministic audit memorandum aggregates spend leakage risks detected across
              supplier master data, purchase orders, incoming invoices, and payment disbursements.
              All amounts cited are backed by exact record citations and rule-verified proofs.
            </p>
          </div>

          {/* Formatted Text Content */}
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200 bg-transparent p-0 border-0 leading-relaxed">
            {memoText || "Loading audit memo..."}
          </pre>
        </div>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 font-mono">
          <span>LedgerLens Autonomous Audit Engine · Built on Google AI</span>
          <span>Proof Trail Intact · Audit Defensible</span>
        </div>
      </div>
    </div>
  );
}
