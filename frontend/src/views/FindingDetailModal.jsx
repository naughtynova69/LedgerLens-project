import React, { useState } from "react";
import {
  ShieldAlert,
  FileText,
  CheckCircle,
  XCircle,
  RotateCcw,
  HelpCircle,
  Sparkles,
  Link2,
  Table,
  User,
  Clock,
  Send,
  AlertTriangle,
} from "lucide-react";
import { Modal } from "../components/Modal";
import { SeverityBadge } from "../components/SeverityBadge";
import { RuleBadge } from "../components/RuleBadge";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatConfidence, formatDate } from "../utils/formatters";

export function FindingDetailModal({
  isOpen,
  onClose,
  finding,
  onMakeDecision,
  isSubmitting,
}) {
  const [reviewer, setReviewer] = useState("Chief Auditor (AP Lead)");
  const [note, setNote] = useState("");
  const [activeTab, setActiveTab] = useState("explanation"); // 'explanation' | 'evidence' | 'sources' | 'decisions'

  if (!finding) return null;

  const expl = finding.explanation || {
    headline: finding.title,
    explanation: finding.summary,
    recommended_action: "Review linked evidence and verify with supplier.",
    limitations: "Human verification required before initiating recovery.",
  };

  const handleDecision = (action) => {
    if (!note.trim()) {
      alert("Please provide an audit note before recording your decision.");
      return;
    }
    onMakeDecision(finding.finding_id, action, reviewer, note);
    setNote("");
  };

  const sources = finding.source_records || {};

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Finding Detail — ${finding.finding_id}`}
      maxWidth="max-w-5xl"
    >
      <div className="space-y-6">
        {/* Top Summary Banner */}
        <div className="p-5 rounded-2xl bg-gradient-to-r from-[#111A2E] to-[#0D1525] border border-slate-800/90 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <SeverityBadge severity={finding.severity} />
              <RuleBadge ruleId={finding.rule_id} full />
              <span className="font-mono text-xs text-slate-400">
                Rule ID: {finding.rule_id}
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              {finding.title}
            </h2>
            <p className="text-xs text-slate-400 font-mono">
              Entity Provenance: {JSON.stringify(finding.entity_refs)}
            </p>
          </div>

          <div className="flex flex-col md:items-end justify-center bg-slate-900/80 p-4 rounded-xl border border-slate-800 shrink-0">
            <span className="text-[11px] uppercase tracking-wider text-slate-400">
              Spend Exposure at Risk
            </span>
            <span className="text-2xl font-bold font-mono text-rose-400">
              {formatCurrency(finding.amount_at_risk, finding.currency)}
            </span>
            <div className="mt-1.5 flex items-center gap-2">
              <span className="text-[11px] text-slate-400">Status:</span>
              <StatusBadge status={finding.status} />
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-800 space-x-4 text-xs font-semibold">
          <button
            onClick={() => setActiveTab("explanation")}
            className={`pb-2.5 flex items-center gap-2 transition-colors relative ${
              activeTab === "explanation"
                ? "text-emerald-400 border-b-2 border-emerald-400"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>Explainability & Narrative</span>
          </button>

          <button
            onClick={() => setActiveTab("sources")}
            className={`pb-2.5 flex items-center gap-2 transition-colors relative ${
              activeTab === "sources"
                ? "text-emerald-400 border-b-2 border-emerald-400"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Table className="w-4 h-4" />
            <span>Side-by-Side Source Records</span>
          </button>

          <button
            onClick={() => setActiveTab("evidence")}
            className={`pb-2.5 flex items-center gap-2 transition-colors relative ${
              activeTab === "evidence"
                ? "text-emerald-400 border-b-2 border-emerald-400"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Link2 className="w-4 h-4" />
            <span>Evidence Chips ({finding.evidence?.length || 0})</span>
          </button>

          <button
            onClick={() => setActiveTab("decisions")}
            className={`pb-2.5 flex items-center gap-2 transition-colors relative ${
              activeTab === "decisions"
                ? "text-emerald-400 border-b-2 border-emerald-400"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Clock className="w-4 h-4" />
            <span>Audit Trail ({finding.decisions?.length || 0})</span>
          </button>
        </div>

        {/* Tab 1: Explainability Card */}
        {activeTab === "explanation" && (
          <div className="space-y-4">
            <div className="p-5 rounded-2xl bg-[#0F172A] border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                  <Sparkles className="w-3.5 h-3.5" />
                  CFO-Ready Audit Narrative
                </span>
                <span className="text-xs font-mono text-slate-400">
                  Confidence Score: {formatConfidence(finding.confidence)}
                </span>
              </div>

              <div className="space-y-2">
                <h3 className="text-lg font-bold text-white">
                  {expl.headline || finding.title}
                </h3>
                <p className="text-sm text-slate-300 leading-relaxed">
                  {expl.explanation || finding.summary}
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3 border-t border-slate-800/80">
                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
                  <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                    <CheckCircle className="w-3.5 h-3.5" />
                    Recommended Action
                  </span>
                  <p className="text-xs text-slate-300 mt-1.5 leading-normal">
                    {expl.recommended_action || "Block payment or raise vendor recovery credit."}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800">
                  <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Auditor Limitations & Verification
                  </span>
                  <p className="text-xs text-slate-300 mt-1.5 leading-normal">
                    {expl.limitations || "Confirm whether this is a legitimate revised invoice before clawback."}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Side-by-Side Source Records */}
        {activeTab === "sources" && (
          <div className="space-y-6">
            {/* Invoices */}
            {sources.invoices && sources.invoices.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <FileText className="w-4 h-4 text-emerald-400" />
                  <span>Invoice Lines in Evidence</span>
                </h4>
                <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">Invoice #</th>
                        <th className="py-2.5 px-3">Date</th>
                        <th className="py-2.5 px-3">Item Description</th>
                        <th className="py-2.5 px-3 text-right">Qty</th>
                        <th className="py-2.5 px-3 text-right">Unit Price</th>
                        <th className="py-2.5 px-3 text-right">Tax %</th>
                        <th className="py-2.5 px-3 text-right">Line Total</th>
                        <th className="py-2.5 px-3 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {sources.invoices.map((inv, idx) => (
                        <tr key={idx} className="hover:bg-slate-800/40">
                          <td className="py-2.5 px-3 font-mono font-bold text-white">
                            {inv.invoice_number}
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">{formatDate(inv.invoice_date)}</td>
                          <td className="py-2.5 px-3 text-slate-200">{inv.item}</td>
                          <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                            {inv.quantity}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                            {formatCurrency(inv.unit_price, inv.currency)}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                            {inv.tax_pct}%
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono font-bold text-rose-400">
                            {formatCurrency(inv.line_total, inv.currency)}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                                inv.status === "paid"
                                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                  : "bg-slate-800 text-slate-300"
                              }`}
                            >
                              {inv.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Contracts */}
            {sources.contracts && sources.contracts.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <FileText className="w-4 h-4 text-amber-400" />
                  <span>Governing Contract Clauses</span>
                </h4>
                <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">Contract ID</th>
                        <th className="py-2.5 px-3">Item</th>
                        <th className="py-2.5 px-3 text-right">Negotiated Price</th>
                        <th className="py-2.5 px-3 text-right">Agreed Tax %</th>
                        <th className="py-2.5 px-3">Start Date</th>
                        <th className="py-2.5 px-3">End Date</th>
                        <th className="py-2.5 px-3 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {sources.contracts.map((c, idx) => (
                        <tr key={idx}>
                          <td className="py-2.5 px-3 font-mono font-bold text-amber-300">
                            {c.contract_id}
                          </td>
                          <td className="py-2.5 px-3 text-slate-200">{c.item}</td>
                          <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-400">
                            {formatCurrency(c.contracted_unit_price, c.currency)}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                            {c.tax_pct}%
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">{formatDate(c.start_date)}</td>
                          <td className="py-2.5 px-3 text-slate-300">{formatDate(c.end_date)}</td>
                          <td className="py-2.5 px-3 text-center">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${
                                c.status === "cancelled"
                                  ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                  : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              }`}
                            >
                              {c.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Purchase Orders */}
            {sources.purchase_orders && sources.purchase_orders.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-400" />
                  <span>Authorized Purchase Order</span>
                </h4>
                <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">PO ID</th>
                        <th className="py-2.5 px-3">Item</th>
                        <th className="py-2.5 px-3 text-right">Authorized Qty</th>
                        <th className="py-2.5 px-3 text-right">Authorized Unit Price</th>
                        <th className="py-2.5 px-3">Order Date</th>
                        <th className="py-2.5 px-3">Expected Delivery</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {sources.purchase_orders.map((po, idx) => (
                        <tr key={idx}>
                          <td className="py-2.5 px-3 font-mono font-bold text-blue-300">
                            {po.po_id}
                          </td>
                          <td className="py-2.5 px-3 text-slate-200">{po.item}</td>
                          <td className="py-2.5 px-3 text-right font-mono font-bold text-white">
                            {po.quantity}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                            {formatCurrency(po.unit_price, po.currency)}
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">{formatDate(po.order_date)}</td>
                          <td className="py-2.5 px-3 text-slate-300">{formatDate(po.expected_delivery)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Payments */}
            {sources.payments && sources.payments.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <FileText className="w-4 h-4 text-purple-400" />
                  <span>Disbursed Bank Payments</span>
                </h4>
                <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-800/60 text-slate-400 uppercase text-[10px] font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">Payment ID</th>
                        <th className="py-2.5 px-3">Linked Invoice</th>
                        <th className="py-2.5 px-3 text-right">Disbursed Amount</th>
                        <th className="py-2.5 px-3">Settlement Date</th>
                        <th className="py-2.5 px-3 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {sources.payments.map((p, idx) => (
                        <tr key={idx}>
                          <td className="py-2.5 px-3 font-mono font-bold text-purple-300">
                            {p.payment_id}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-slate-300">{p.invoice_number}</td>
                          <td className="py-2.5 px-3 text-right font-mono font-bold text-rose-400">
                            {formatCurrency(p.amount, p.currency)}
                          </td>
                          <td className="py-2.5 px-3 text-slate-300">{formatDate(p.payment_date)}</td>
                          <td className="py-2.5 px-3 text-center">
                            <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold bg-purple-500/10 text-purple-300 border border-purple-500/20">
                              {p.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Evidence Chips */}
        {activeTab === "evidence" && (
          <div className="space-y-4">
            <p className="text-xs text-slate-400">
              Each citation below is an immutable <code className="text-emerald-400 font-mono">EvidenceRef</code> recorded by the deterministic audit rule.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(finding.evidence || []).map((ev, i) => (
                <div
                  key={i}
                  className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start gap-3"
                >
                  <div className="p-2 rounded-lg bg-slate-800 text-slate-400">
                    <Link2 className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                        {ev.source}
                      </span>
                      <span className="font-mono text-xs font-semibold text-white truncate">
                        {ev.record_id}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">
                      Field: <span className="font-mono text-slate-300">{ev.field}</span>
                    </p>
                    <p className="text-xs font-mono font-bold text-emerald-300">
                      Value: {ev.value}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 4: Audit Trail */}
        {activeTab === "decisions" && (
          <div className="space-y-4">
            {(!finding.decisions || finding.decisions.length === 0) ? (
              <div className="p-8 text-center text-slate-400 text-xs bg-slate-900/40 rounded-xl border border-slate-800">
                No formal decisions recorded on this finding yet.
              </div>
            ) : (
              <div className="space-y-3">
                {finding.decisions.map((d, i) => (
                  <div
                    key={i}
                    className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <User className="w-3.5 h-3.5 text-slate-400" />
                        <span className="font-semibold text-white">{d.reviewer}</span>
                        <span className="text-slate-500">·</span>
                        <StatusBadge status={d.action} />
                      </div>
                      <span className="font-mono text-[11px] text-slate-500">
                        {d.created_at}
                      </span>
                    </div>
                    {d.note && (
                      <p className="text-xs text-slate-300 italic pl-5 border-l-2 border-slate-700">
                        "{d.note}"
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Decision Action Workflow */}
        <div className="p-5 rounded-2xl bg-[#0B111F] border border-slate-800 space-y-4 pt-5">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-white flex items-center gap-2">
              <Send className="w-4 h-4 text-emerald-400" />
              <span>Record Reviewer Decision</span>
            </h4>
            <span className="text-[11px] text-slate-400">
              Updates status & writes tamper-evident audit row
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Auditor / Reviewer Name:
              </label>
              <input
                type="text"
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs sm:text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">
                Decision Note & Justification:
              </label>
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="E.g. Confirmed duplicate with supplier; credit memo requested."
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs sm:text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              onClick={() => handleDecision("reject")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs transition-all shadow-md shadow-rose-950/30 disabled:opacity-50"
            >
              <XCircle className="w-4 h-4" />
              <span>Block / Reject Payment</span>
            </button>

            <button
              onClick={() => handleDecision("recovery")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs transition-all shadow-md shadow-purple-950/30 disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Raise Recovery Task</span>
            </button>

            <button
              onClick={() => handleDecision("request_docs")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs transition-all shadow-md shadow-sky-950/30 disabled:opacity-50"
            >
              <HelpCircle className="w-4 h-4" />
              <span>Request Vendor Docs</span>
            </button>

            <button
              onClick={() => handleDecision("approve")}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-all shadow-md shadow-emerald-950/30 disabled:opacity-50"
            >
              <CheckCircle className="w-4 h-4" />
              <span>Approve Exception</span>
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
