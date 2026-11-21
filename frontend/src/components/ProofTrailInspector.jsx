import React, { useState } from "react";
import { api } from "../api";
import { StatusBadge } from "./StatusBadge";
import { RuleBadge } from "./RuleBadge";
import { SeverityBadge } from "./SeverityBadge";
import { EvidenceGraphCanvas } from "./EvidenceGraphCanvas";
import { PdfEvidencePreview } from "./PdfEvidencePreview";
import { formatCurrency, formatConfidence } from "../utils/formatters";
import { useAccountMemory } from "../context/AccountMemoryContext";

const DEFAULT_NOTES = {
  recovery: "Payment held and recovery initiated via AP workstation.",
  reject: "Disputed with vendor pending credit note or revised invoice.",
  approve: "Placed on hold / approved after review.",
};

export function ProofTrailInspector({
  finding,
  onMakeDecision,
  isSubmitting,
  onToast,
}) {
  const { reviewerLabel } = useAccountMemory();
  const [note, setNote] = useState("");
  const [copyingDispute, setCopyingDispute] = useState(false);
  const [evidenceTab, setEvidenceTab] = useState("table");

  if (!finding) {
    return (
      <div className="bg-white border border-[#E2E8F0] rounded-md p-10 text-center">
        <p className="text-sm font-medium text-slate-900">Select an exception</p>
        <p className="text-xs text-slate-500 mt-1">
          Choose any row on the left or press{" "}
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-slate-100 border border-[#E2E8F0] rounded">
            j
          </kbd>{" "}
          /{" "}
          <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-slate-100 border border-[#E2E8F0] rounded">
            k
          </kbd>{" "}
          to inspect its proof trail and take action.
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
  const vendors = sources.vendors || [];

  const vendorLabel =
    vendors[0]?.vendor_name ||
    finding.entity_refs?.vendor_id ||
    "Vendor";

  const handleAction = async (action) => {
    const finalNote = note.trim() || DEFAULT_NOTES[action] || "Reviewed in LedgerLens.";
    await onMakeDecision(finding.finding_id, action, reviewerLabel, finalNote);
    setNote("");
  };

  const handleCopyDisputeEmail = async () => {
    setCopyingDispute(true);
    try {
      const packet = await api.getDisputePacket(finding.finding_id);
      const emailText = `Subject: ${packet.subject}\n\n${packet.body_text}`;
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(emailText);
      }
      if (onToast) {
        onToast(
          `Dispute email for ${finding.finding_id} copied to clipboard.`,
          "success",
          "Dispute Email Copied"
        );
      }
    } catch (err) {
      if (onToast) {
        onToast(
          err.message || "Could not generate dispute packet.",
          "error",
          "Dispute Copy Failed"
        );
      }
    } finally {
      setCopyingDispute(false);
    }
  };

  const primaryInvoice = invoices[0];
  const primaryContract = contracts[0];
  const primaryPo = pos[0];

  const evidenceBatchId =
    finding.batch?.batch_id || finding.batch_id || primaryInvoice?.batch_id || null;
  const evidenceFileName =
    finding.batch?.file_name || finding.file_name || primaryInvoice?.file_name || "";
  const evidenceMimeType =
    finding.batch?.mime_type || finding.mime_type || primaryInvoice?.mime_type || "";
  const hasDocumentEvidence =
    Boolean(evidenceBatchId) &&
    (evidenceMimeType.toLowerCase().includes("pdf") ||
      evidenceMimeType.toLowerCase().startsWith("image/") ||
      /\.(pdf|png|jpe?g|webp|gif|bmp)$/i.test(evidenceFileName));

  const invoiceRef =
    invoices.length > 1
      ? invoices.map((i) => i.invoice_number).filter(Boolean).join(", ")
      : primaryInvoice?.invoice_number || "—";

  const invoiceDetail = primaryInvoice
    ? `${primaryInvoice.item || "Line item"} · ${primaryInvoice.quantity} × ${formatCurrency(
        primaryInvoice.unit_price,
        primaryInvoice.currency
      )} (Tax ${primaryInvoice.tax_pct ?? 0}%)`
    : "No linked invoice line";

  const invoiceAmount = primaryInvoice
    ? formatCurrency(primaryInvoice.line_total, primaryInvoice.currency)
    : "—";

  const contractRef = primaryContract?.contract_id || "—";
  const contractDetail = primaryContract
    ? `${primaryContract.item || "Term"} · Disc ${primaryContract.discount_pct ?? 0}% · Tax ${
        primaryContract.tax_pct ?? 0
      }% · ${primaryContract.status || "active"}`
    : "No governing contract";
  const contractAmount = primaryContract
    ? formatCurrency(primaryContract.contracted_unit_price, primaryContract.currency)
    : "—";

  const poRef = primaryPo?.po_id || "—";
  const poDetail = primaryPo
    ? `${primaryPo.item || "PO item"} · Qty ${primaryPo.quantity} · ${primaryPo.status || "open"}`
    : "No referenced PO";
  const poAmount = primaryPo
    ? formatCurrency(primaryPo.unit_price, primaryPo.currency)
    : "—";

  const billedNum = primaryInvoice?.line_total ?? primaryInvoice?.unit_price ?? null;
  const billedDisplay =
    billedNum !== null
      ? formatCurrency(billedNum, primaryInvoice?.currency || finding.currency)
      : "—";

  const refUnitNum = primaryContract?.contracted_unit_price ?? primaryPo?.unit_price ?? null;
  const refCurrency = primaryContract?.currency || primaryPo?.currency || finding.currency;
  const refDisplay = refUnitNum !== null ? formatCurrency(refUnitNum, refCurrency) : "—";
  const refLabel = primaryContract ? `Contract ${contractRef}` : primaryPo ? `PO ${poRef}` : "No reference";

  const variancePct =
    billedNum && billedNum > 0 && finding.amount_at_risk > 0
      ? `+${((finding.amount_at_risk / billedNum) * 100).toFixed(1)}%`
      : null;

  const plainEnglishSummary =
    expl.explanation ||
    finding.summary ||
    expl.headline ||
    "Deterministic rule discrepancy identified across source records.";

  const tabs = [
    { id: "table", label: "Line-Item Proof" },
    { id: "pdf", label: "Source PDF", dot: hasDocumentEvidence },
    { id: "graph", label: "Graph Path" },
  ];

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-md divide-y divide-[#E2E8F0]">
      {/* Pinned Header & Primary Decision Controls */}
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-1 min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[11px] font-medium text-slate-500">
                {finding.finding_id}
              </span>
              <span className="text-slate-300">·</span>
              <span className="text-xs font-medium text-slate-900 truncate">
                {vendorLabel}
              </span>
              <RuleBadge ruleId={finding.rule_id} />
              <SeverityBadge severity={finding.severity} />
              <StatusBadge status={finding.status} />
            </div>
            <h2 className="text-[15px] font-semibold text-slate-900 tracking-tight leading-snug">
              {finding.title}
            </h2>
          </div>
        </div>

        <p className="text-xs text-slate-600 leading-relaxed">
          {expl.headline && expl.headline !== finding.title ? `${expl.headline}. ` : ""}
          {plainEnglishSummary}
        </p>

        {/* Pinned Decision Actions */}
        <div className="pt-1 space-y-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={() => handleAction("recovery")}
              disabled={isSubmitting}
              className="px-3 py-1.5 rounded text-xs font-medium bg-[#047857] hover:bg-[#065F46] text-white transition-colors disabled:opacity-50"
            >
              Approve Recovery
            </button>

            <button
              type="button"
              onClick={() => handleAction("reject")}
              disabled={isSubmitting}
              className="px-3 py-1.5 rounded text-xs font-medium bg-[#B91C1C] hover:bg-[#991B1B] text-white transition-colors disabled:opacity-50"
            >
              Dispute
            </button>

            <button
              type="button"
              onClick={() => handleAction("approve")}
              disabled={isSubmitting}
              className="px-3 py-1.5 rounded text-xs font-medium bg-white text-slate-700 border border-[#E2E8F0] hover:bg-slate-50 transition-colors disabled:opacity-50"
            >
              Hold
            </button>

            <button
              type="button"
              onClick={handleCopyDisputeEmail}
              disabled={copyingDispute}
              className="px-2.5 py-1.5 rounded text-xs font-medium bg-white text-slate-600 border border-[#E2E8F0] hover:text-slate-900 hover:bg-slate-50 transition-colors disabled:opacity-50 sm:ml-auto"
            >
              {copyingDispute ? "Copying…" : "Copy Dispute Email"}
            </button>
          </div>

          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add audit note (optional)…"
            aria-label="Audit note"
            className="w-full px-2.5 py-1.5 bg-[#F8FAFC] border border-[#E2E8F0] rounded text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-400 focus:bg-white"
          />
        </div>
      </div>

      {/* 3-Column Hairline Delta Comparison Strip */}
      <div className="grid grid-cols-3 divide-x divide-[#E2E8F0] bg-[#F8FAFC]">
        <div className="px-3.5 py-2.5 min-w-0">
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
            Billed
          </div>
          <div className="text-[17px] font-semibold font-mono tabular-nums text-slate-900 mt-0.5 truncate">
            {billedDisplay}
          </div>
          <div className="text-[11px] font-mono text-slate-500 truncate">
            {invoiceRef}
          </div>
        </div>

        <div className="px-3.5 py-2.5 min-w-0">
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
            Contract / PO
          </div>
          <div className="text-[17px] font-semibold font-mono tabular-nums text-slate-900 mt-0.5 truncate">
            {refDisplay}
          </div>
          <div className="text-[11px] font-mono text-slate-500 truncate">
            {refLabel}
          </div>
        </div>

        <div className="px-3.5 py-2.5 min-w-0">
          <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
            Variance
          </div>
          <div className="text-[17px] font-semibold font-mono tabular-nums text-[#B91C1C] mt-0.5 truncate">
            {formatCurrency(finding.amount_at_risk, finding.currency)}
          </div>
          <div className="text-[11px] font-mono tabular-nums text-slate-500 truncate">
            {variancePct ? `${variancePct} · ` : ""}
            {formatConfidence(finding.confidence)} conf
          </div>
        </div>
      </div>

      {/* Tabbed Evidence Inspector */}
      <div className="p-4 space-y-3">
        <div className="flex items-center gap-1 border-b border-[#E2E8F0] pb-2">
          {tabs.map((tab) => {
            const active = evidenceTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setEvidenceTab(tab.id)}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                  active
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
              >
                <span>{tab.label}</span>
                {tab.dot && (
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      active ? "bg-emerald-400" : "bg-[#047857]"
                    }`}
                    title="Source document available"
                  />
                )}
              </button>
            );
          })}
        </div>

        {evidenceTab === "table" && (
          <div className="space-y-3">
            <div className="border border-[#E2E8F0] rounded-md overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F8FAFC] border-b border-[#E2E8F0] text-slate-500">
                  <tr>
                    <th className="py-2 px-3 font-medium">Source</th>
                    <th className="py-2 px-3 font-medium">Ref</th>
                    <th className="py-2 px-3 font-medium">Line / Terms</th>
                    <th className="py-2 px-3 font-medium text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  <tr>
                    <td className="py-2 px-3 font-medium text-slate-900 whitespace-nowrap">
                      Invoice
                    </td>
                    <td className="py-2 px-3 font-mono text-slate-900 whitespace-nowrap">
                      {invoiceRef}
                    </td>
                    <td
                      className="py-2 px-3 text-slate-600 max-w-[180px] truncate"
                      title={invoiceDetail}
                    >
                      {invoiceDetail}
                    </td>
                    <td className="py-2 px-3 font-mono tabular-nums text-right font-medium text-[#B91C1C] whitespace-nowrap">
                      {invoiceAmount}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 px-3 font-medium text-slate-900 whitespace-nowrap">
                      Contract
                    </td>
                    <td className="py-2 px-3 font-mono text-slate-900 whitespace-nowrap">
                      {contractRef}
                    </td>
                    <td
                      className="py-2 px-3 text-slate-600 max-w-[180px] truncate"
                      title={contractDetail}
                    >
                      {contractDetail}
                    </td>
                    <td className="py-2 px-3 font-mono tabular-nums text-right font-medium text-slate-900 whitespace-nowrap">
                      {contractAmount}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-2 px-3 font-medium text-slate-900 whitespace-nowrap">
                      PO
                    </td>
                    <td className="py-2 px-3 font-mono text-slate-900 whitespace-nowrap">
                      {poRef}
                    </td>
                    <td
                      className="py-2 px-3 text-slate-600 max-w-[180px] truncate"
                      title={poDetail}
                    >
                      {poDetail}
                    </td>
                    <td className="py-2 px-3 font-mono tabular-nums text-right font-medium text-slate-900 whitespace-nowrap">
                      {poAmount}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Progressive Disclosure: Technical Proof & Audit Trail */}
            <details className="border border-[#E2E8F0] rounded-md px-3 py-2.5 group bg-[#F8FAFC]/50">
              <summary className="cursor-pointer text-xs font-medium text-slate-600 hover:text-slate-900 select-none list-none flex items-center justify-between">
                <span>Audit proof &amp; technical trail</span>
                <span className="font-mono text-[11px] text-slate-400 group-open:hidden">
                  Expand
                </span>
                <span className="font-mono text-[11px] text-slate-400 hidden group-open:inline">
                  Collapse
                </span>
              </summary>

              <div className="mt-3 space-y-3">
                <div className="text-[11px] text-slate-600 flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#E2E8F0]">
                  <span>
                    Rule {finding.rule_id} · Narrative: Gemini Vision
                    {expl.generated_without_gemini ? " (Offline Proof Mode)" : ""}
                  </span>
                  <span className="font-mono">
                    Action: {finding.recommended_action || proofTrail.recommended_action || "HOLD_PAYMENT"}
                  </span>
                </div>

                {Object.keys(mathObj).length > 0 && (
                  <div className="p-2.5 rounded bg-white border border-[#E2E8F0] text-[11px] font-mono tabular-nums text-slate-900 space-y-1">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      PROOF MATH
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1">
                      {Object.entries(mathObj).map(([k, v]) => (
                        <span key={k}>
                          <span className="text-slate-500">{k}=</span>
                          <span>{String(v)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {(finding.evidence || []).length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                      Evidence Citations
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {finding.evidence.map((ev, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white border border-[#E2E8F0] text-[11px] font-mono text-slate-700"
                        >
                          <span className="font-medium text-slate-900">{ev.source}</span>
                          <span>{ev.record_id}</span>
                          <span className="text-slate-400">/</span>
                          <span>{ev.field}:</span>
                          <span className="font-medium text-slate-900">{ev.value}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {finding.decisions?.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                      Decision History ({finding.decisions.length})
                    </div>
                    <div className="divide-y divide-[#E2E8F0] border border-[#E2E8F0] rounded bg-white">
                      {finding.decisions.map((d, idx) => (
                        <div
                          key={idx}
                          className="px-2.5 py-1.5 flex flex-wrap items-center justify-between gap-2 text-xs"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <StatusBadge status={d.action} />
                            <span className="font-medium text-slate-900">{d.reviewer}</span>
                            {d.note && <span className="text-slate-500 truncate">{d.note}</span>}
                          </div>
                          <span className="font-mono text-[11px] text-slate-500">
                            {d.created_at}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </details>
          </div>
        )}

        {evidenceTab === "pdf" && (
          <PdfEvidencePreview
            batchId={evidenceBatchId}
            fileName={evidenceFileName}
            mimeType={evidenceMimeType}
          />
        )}

        {evidenceTab === "graph" && (
          <EvidenceGraphCanvas findingId={finding.finding_id} height={320} />
        )}
      </div>

      {/* Subtle Keyboard Shortcut Footer */}
      <div className="px-4 py-2 bg-[#F8FAFC] flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 font-mono text-[10px] bg-white border border-[#E2E8F0] rounded text-slate-700">
              j
            </kbd>
            <kbd className="px-1.5 py-0.5 font-mono text-[10px] bg-white border border-[#E2E8F0] rounded text-slate-700">
              k
            </kbd>
            <span>Navigate</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 font-mono text-[10px] bg-white border border-[#E2E8F0] rounded text-slate-700">
              a
            </kbd>
            <span>/</span>
            <kbd className="px-1.5 py-0.5 font-mono text-[10px] bg-white border border-[#E2E8F0] rounded text-slate-700">
              r
            </kbd>
            <span>Recover</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 font-mono text-[10px] bg-white border border-[#E2E8F0] rounded text-slate-700">
              d
            </kbd>
            <span>Dispute</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 font-mono text-[10px] bg-white border border-[#E2E8F0] rounded text-slate-700">
              /
            </kbd>
            <span>Search</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 font-mono text-[10px] bg-white border border-[#E2E8F0] rounded text-slate-700">
              Esc
            </kbd>
            <span>Clear</span>
          </span>
        </div>
      </div>
    </div>
  );
}
