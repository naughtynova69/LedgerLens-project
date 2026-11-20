import React, { useState } from "react";
import {
  Sparkles,
  Scale,
  FileText,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Link2,
  Clock,
  ShieldAlert,
} from "lucide-react";
import { SeverityBadge } from "./SeverityBadge";
import { RuleBadge } from "./RuleBadge";
import { StatusBadge } from "./StatusBadge";
import { formatCurrency, formatConfidence, formatDate } from "../utils/formatters";

export function ProofTrailInspector({ finding, onMakeDecision, isSubmitting }) {
  const [reviewer, setReviewer] = useState("Vijay (AP Lead)");
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState("");

  if (!finding) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-8 text-center space-y-2 shadow-sm">
        <ShieldAlert className="w-8 h-8 text-slate-400 mx-auto" />
        <h3 className="text-sm font-semibold text-slate-900">Select a Finding to Inspect</h3>
        <p className="text-xs text-slate-500">
          Click any exception row to view its 3-way Invoice vs. Contract vs. PO proof trail and CFO explanation.
        </p>
      </div>
    );
  }

  const expl = finding.explanation || {};
  const proofTrail = finding.proof_trail || {};
  const mathObj = proofTrail.math || {};
  const sources = finding.source_records || {};
  const invoices = sources.invoices || [];
  const contracts = sources.contracts || [];
  const pos = sources.purchase_orders || [];
  const payments = sources.payments || [];

  const handleAction = async (action) => {
    const trimmed = note.trim();
    if (!trimmed) {
      setNoteError("Please enter a short audit note before submitting a decision.");
      return;
    }
    setNoteError("");
    await onMakeDecision(finding.finding_id, action, reviewer.trim() || "AP Lead", trimmed);
    setNote("");
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
      {/* Inspector Header */}
      <div className="p-5 border-b border-slate-200 bg-slate-50/70 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-200">
              {finding.finding_id}
            </span>
            <RuleBadge ruleId={finding.rule_id} full />
            <SeverityBadge severity={finding.severity} />
            <StatusBadge status={finding.status} />
          </div>
          <div className="text-right">
            <div className="text-xl font-bold font-mono tabular-nums text-[#DC2626]">
              {formatCurrency(finding.amount_at_risk, finding.currency)}
            </div>
            <div className="text-[11px] font-mono tabular-nums text-slate-500">
              Confidence: {formatConfidence(finding.confidence)} · Action:{" "}
              <span className="font-semibold text-slate-700">
                {finding.recommended_action || proofTrail.recommended_action || "HOLD_PAYMENT"}
              </span>
            </div>
          </div>
        </div>

        <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
          {finding.title}
        </h2>
      </div>

      <div className="p-5 space-y-5 overflow-y-auto">
        {/* CFO-Ready Explanation Card */}
        <div className="p-4 rounded-xl border border-slate-200 bg-[#F8FAFC] space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-800">
              <Sparkles className="w-3.5 h-3.5 text-[#4F46E5]" />
              CFO-Ready Explanation
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">
              <Scale className="w-3 h-3" />
              Decision: Deterministic Rule {finding.rule_id} · Narrative: Gemini 4 Carbon
              {expl.generated_without_gemini ? " (Offline Proof Mode)" : ""}
            </span>
          </div>

          <p className="text-sm font-semibold text-slate-900">
            {expl.headline || finding.title}
          </p>
          <p className="text-xs sm:text-sm text-slate-700 leading-relaxed">
            {expl.explanation || finding.summary}
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div className="p-3 rounded-lg bg-[#ECFDF5] border border-[#A7F3D0]">
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#059669]">
                Recommended Action
              </div>
              <p className="text-xs text-slate-700 mt-1">
                {expl.recommended_action || "Hold disbursement and reconcile against source records."}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-[#FFFBEB] border border-[#FDE68A]">
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#D97706] flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" />
                Verification Scope
              </div>
              <p className="text-xs text-slate-700 mt-1">
                {expl.limitations || "Confirm vendor credit memo or supporting PO documentation."}
              </p>
            </div>
          </div>
        </div>

        {/* 3-Way Evidence Diff Card: Invoice Line vs Contract Clause vs PO Line */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-slate-600" />
              3-Way Evidence Diff Card (Invoice vs. Contract vs. PO)
            </h3>
            {payments.length > 0 && (
              <span className="text-[11px] font-mono font-semibold text-[#DC2626] bg-[#FEF2F2] border border-[#FECACA] px-2 py-0.5 rounded">
                {payments.length} Settled Payment(s) Linked
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Invoice Column */}
            <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#DC2626]">
                Invoice Line(s)
              </div>
              {invoices.length === 0 ? (
                <p className="text-xs text-slate-400">No invoice row joined</p>
              ) : (
                invoices.map((inv, idx) => (
                  <div key={idx} className="text-xs space-y-1 border-t first:border-t-0 border-slate-100 pt-1.5 first:pt-0">
                    <div className="font-mono font-bold text-slate-900">{inv.invoice_number}</div>
                    <div className="text-slate-600 truncate" title={inv.item}>{inv.item}</div>
                    <div className="font-mono tabular-nums text-slate-800">
                      {inv.quantity} × {formatCurrency(inv.unit_price, inv.currency)} (Tax {inv.tax_pct}%)
                    </div>
                    <div className="font-mono tabular-nums font-bold text-[#DC2626]">
                      Total: {formatCurrency(inv.line_total, inv.currency)}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Date: {formatDate(inv.invoice_date)} · {inv.status}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Contract Column */}
            <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#059669]">
                Contract Clause
              </div>
              {contracts.length === 0 ? (
                <p className="text-xs text-slate-400">No governing contract line</p>
              ) : (
                contracts.map((c, idx) => (
                  <div key={idx} className="text-xs space-y-1">
                    <div className="font-mono font-bold text-slate-900">{c.contract_id}</div>
                    <div className="text-slate-600 truncate" title={c.item}>{c.item}</div>
                    <div className="font-mono tabular-nums font-semibold text-[#059669]">
                      Rate: {formatCurrency(c.contracted_unit_price, c.currency)}
                    </div>
                    <div className="font-mono tabular-nums text-slate-700">
                      Tax: {c.tax_pct}% · Disc: {c.discount_pct}%
                    </div>
                    <div className="text-[11px] text-slate-500">
                      End: {c.end_date || "—"} · <span className="uppercase font-semibold">{c.status}</span>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* PO Column */}
            <div className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#4F46E5]">
                Authorized PO Line
              </div>
              {pos.length === 0 ? (
                <p className="text-xs text-slate-400">No PO referenced</p>
              ) : (
                pos.map((po, idx) => (
                  <div key={idx} className="text-xs space-y-1">
                    <div className="font-mono font-bold text-slate-900">{po.po_id}</div>
                    <div className="text-slate-600 truncate" title={po.item}>{po.item}</div>
                    <div className="font-mono tabular-nums font-semibold text-slate-900">
                      Qty: {po.quantity} @ {formatCurrency(po.unit_price, po.currency)}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Exp. Delivery: {po.expected_delivery || "—"}
                    </div>
                    <div className="text-[11px] text-slate-500 uppercase font-semibold">
                      Status: {po.status}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Deterministic Delta Math Bar */}
          {Object.keys(mathObj).length > 0 && (
            <div className="p-3 rounded-lg bg-slate-900 text-slate-100 text-xs font-mono tabular-nums flex flex-wrap gap-x-4 gap-y-1">
              <span className="text-emerald-400 font-bold">PROOF MATH:</span>
              {Object.entries(mathObj).map(([k, v]) => (
                <span key={k}>
                  <span className="text-slate-400">{k}=</span>
                  <span className="text-white">{String(v)}</span>
                </span>
              ))}
            </div>
          )}

          {/* EvidenceRef Chips */}
          <div className="flex flex-wrap gap-2 pt-1">
            {(finding.evidence || []).map((ev, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 border border-slate-200 text-[11px] font-mono text-slate-700"
              >
                <Link2 className="w-3 h-3 text-slate-500" />
                <span className="font-semibold">{ev.source}</span>
                <span>{ev.record_id}</span>
                <span className="text-slate-400">/</span>
                <span>{ev.field}:</span>
                <span className="font-bold text-slate-900">{ev.value}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Decision History for this Finding */}
        {finding.decisions?.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              Decision History ({finding.decisions.length})
            </h4>
            <div className="space-y-1.5">
              {finding.decisions.map((d, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex flex-wrap items-center justify-between gap-2 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <StatusBadge status={d.action} />
                    <span className="font-semibold text-slate-900">{d.reviewer}</span>
                    {d.note && <span className="text-slate-600">"{d.note}"</span>}
                  </div>
                  <span className="font-mono text-[11px] text-slate-500">{d.created_at}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reviewer Action Bar */}
        <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
              Reviewer Action Bar
            </span>
            <span className="text-[11px] text-slate-500">
              Appends immutable record to audit log
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Reviewer Name
              </label>
              <input
                type="text"
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
                className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:border-emerald-600"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Audit Note
              </label>
              <input
                type="text"
                value={note}
                onChange={(e) => {
                  setNote(e.target.value);
                  if (noteError) setNoteError("");
                }}
                placeholder="E.g. Duplicate verified; initiate vendor credit recovery."
                className="w-full px-3 py-1.5 bg-white border border-slate-300 rounded-lg text-xs text-slate-900 focus:outline-none focus:border-emerald-600"
              />
            </div>
          </div>

          {noteError && (
            <p className="text-xs font-medium text-[#DC2626]">{noteError}</p>
          )}

          <div className="flex flex-wrap items-center gap-2.5 pt-1">
            <button
              onClick={() => handleAction("recovery")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#DC2626] hover:bg-red-700 text-white text-xs font-semibold transition-colors disabled:opacity-50"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Hold / Recover</span>
            </button>

            <button
              onClick={() => handleAction("approve")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#059669] hover:bg-[#047857] text-white text-xs font-semibold transition-colors disabled:opacity-50"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Approve (False Positive)</span>
            </button>

            <button
              onClick={() => handleAction("reject")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold transition-colors disabled:opacity-50"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Reject / Dispute</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
