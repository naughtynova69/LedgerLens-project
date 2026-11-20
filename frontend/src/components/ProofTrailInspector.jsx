import React, { useState } from "react";
import { api } from "../api";
import { StatusBadge } from "./StatusBadge";
import { RuleBadge } from "./RuleBadge";
import { SeverityBadge } from "./SeverityBadge";
import { PdfEvidencePreview } from "./PdfEvidencePreview";
import { formatCurrency, formatConfidence } from "../utils/formatters";

const DEFAULT_NOTES = {
  recovery: "Payment held and recovery initiated via AP workstation.",
  reject: "Disputed with vendor pending credit note or revised invoice.",
  approve: "Approved as valid exception / false positive.",
};

export function ProofTrailInspector({
  finding,
  onMakeDecision,
  isSubmitting,
  onToast,
}) {
  const [note, setNote] = useState("");
  const [copyingDispute, setCopyingDispute] = useState(false);
  const [showEvidencePreview, setShowEvidencePreview] = useState(false);

  if (!finding) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-10 text-center">
        <p className="text-sm font-medium text-[#111827]">Select an exception</p>
        <p className="text-xs text-[#6B7280] mt-1">
          Choose any row on the left to inspect its 3-way match and take action.
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
    await onMakeDecision(finding.finding_id, action, "Vijay (AP Lead)", finalNote);
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

  const plainEnglishSummary =
    expl.explanation ||
    finding.summary ||
    expl.headline ||
    "Deterministic rule discrepancy identified across source records.";

  return (
    <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-200">
      {/* Header & Above-the-Fold Explanation */}
      <div className="p-5 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1.5 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-medium text-[#6B7280]">
                {finding.finding_id}
              </span>
              <span className="text-xs text-gray-300">·</span>
              <span className="text-xs font-medium text-[#111827]">{vendorLabel}</span>
              <RuleBadge ruleId={finding.rule_id} />
              {finding.severity?.toLowerCase() === "critical" && (
                <SeverityBadge severity={finding.severity} />
              )}
              <StatusBadge status={finding.status} />
            </div>
            <h2 className="text-base font-semibold text-[#111827] tracking-tight">
              {finding.title}
            </h2>
          </div>

          <div className="text-right shrink-0">
            <div className="text-xl font-semibold font-mono tabular-nums text-[#B91C1C]">
              {formatCurrency(finding.amount_at_risk, finding.currency)}
            </div>
            <div className="text-[11px] font-mono tabular-nums text-[#6B7280] mt-0.5">
              At risk · {formatConfidence(finding.confidence)} conf
            </div>
          </div>
        </div>

        <p className="text-xs sm:text-sm text-[#6B7280] leading-relaxed">
          {expl.headline && expl.headline !== finding.title ? `${expl.headline}. ` : ""}
          {plainEnglishSummary}
        </p>
      </div>

      {/* 3-Row Number Comparison Table */}
      <div className="p-5">
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#FAFAFA] border-b border-gray-200 text-[#6B7280]">
              <tr>
                <th className="py-2 px-3 font-medium">Source</th>
                <th className="py-2 px-3 font-medium">Ref</th>
                <th className="py-2 px-3 font-medium">Line / Terms</th>
                <th className="py-2 px-3 font-medium text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              <tr>
                <td className="py-2.5 px-3 font-medium text-[#111827] whitespace-nowrap">
                  Invoice
                </td>
                <td className="py-2.5 px-3 font-mono text-[#111827] whitespace-nowrap">
                  {invoiceRef}
                </td>
                <td className="py-2.5 px-3 text-[#6B7280] max-w-[220px] truncate" title={invoiceDetail}>
                  {invoiceDetail}
                </td>
                <td className="py-2.5 px-3 font-mono tabular-nums text-right font-medium text-[#B91C1C] whitespace-nowrap">
                  {invoiceAmount}
                </td>
              </tr>
              <tr>
                <td className="py-2.5 px-3 font-medium text-[#111827] whitespace-nowrap">
                  Contract
                </td>
                <td className="py-2.5 px-3 font-mono text-[#111827] whitespace-nowrap">
                  {contractRef}
                </td>
                <td className="py-2.5 px-3 text-[#6B7280] max-w-[220px] truncate" title={contractDetail}>
                  {contractDetail}
                </td>
                <td className="py-2.5 px-3 font-mono tabular-nums text-right font-medium text-[#111827] whitespace-nowrap">
                  {contractAmount}
                </td>
              </tr>
              <tr>
                <td className="py-2.5 px-3 font-medium text-[#111827] whitespace-nowrap">
                  PO
                </td>
                <td className="py-2.5 px-3 font-mono text-[#111827] whitespace-nowrap">
                  {poRef}
                </td>
                <td className="py-2.5 px-3 text-[#6B7280] max-w-[220px] truncate" title={poDetail}>
                  {poDetail}
                </td>
                <td className="py-2.5 px-3 font-mono tabular-nums text-right font-medium text-[#111827] whitespace-nowrap">
                  {poAmount}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 1-Line Action Bar */}
      <div className="p-5 space-y-3 bg-[#FAFAFA]/50">
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add audit note (optional)..."
            aria-label="Audit note"
            className="flex-1 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs text-[#111827] placeholder-gray-400 focus:outline-none focus:border-gray-400"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => handleAction("recovery")}
            disabled={isSubmitting}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-50/80 text-red-700 border border-red-200 hover:bg-red-100/70 transition-colors disabled:opacity-50"
          >
            Hold / Recover
          </button>

          <button
            type="button"
            onClick={() => handleAction("reject")}
            disabled={isSubmitting}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white text-[#111827] border border-gray-200 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            Dispute
          </button>

          <button
            type="button"
            onClick={handleCopyDisputeEmail}
            disabled={copyingDispute}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white text-gray-700 border border-gray-200 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            {copyingDispute ? "Copying..." : "Copy Dispute Email"}
          </button>

          <button
            type="button"
            onClick={() => handleAction("approve")}
            disabled={isSubmitting}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-50/80 text-emerald-700 border border-emerald-200 hover:bg-emerald-100/70 transition-colors disabled:opacity-50 sm:ml-auto"
          >
            Approve
          </button>
        </div>
      </div>

      {/* Inline PDF / Image Evidence Preview (when batch has an uploaded document) */}
      {hasDocumentEvidence && (
        <div className="p-5 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-[#111827]">
              Source Document Evidence
            </span>
            <button
              type="button"
              onClick={() => setShowEvidencePreview((v) => !v)}
              className="px-2.5 py-1 rounded-md text-[11px] font-medium border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors"
            >
              {showEvidencePreview ? "Hide Preview" : "Show Preview"}
            </button>
          </div>
          {showEvidencePreview && (
            <PdfEvidencePreview
              batchId={evidenceBatchId}
              fileName={evidenceFileName}
              mimeType={evidenceMimeType}
            />
          )}
        </div>
      )}

      {/* Progressive Disclosure: Technical Proof & Audit Trail */}
      <details className="p-5 group">
        <summary className="cursor-pointer text-xs font-medium text-[#6B7280] hover:text-[#111827] select-none list-none flex items-center justify-between">
          <span>Audit proof &amp; technical trail</span>
          <span className="font-mono text-[11px] text-gray-400 group-open:hidden">
            Expand
          </span>
          <span className="font-mono text-[11px] text-gray-400 hidden group-open:inline">
            Collapse
          </span>
        </summary>

        <div className="mt-4 space-y-4">
          <div className="text-xs text-[#6B7280] flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-gray-200">
            <span>
              Decision: Deterministic Rule {finding.rule_id} · Narrative: Gemini 3.8 Vision Flash
              {expl.generated_without_gemini ? " (Offline Proof Mode)" : ""}
            </span>
            <span className="font-mono text-[11px]">
              Action: {finding.recommended_action || proofTrail.recommended_action || "HOLD_PAYMENT"}
            </span>
          </div>

          {Object.keys(mathObj).length > 0 && (
            <div className="p-3 rounded-lg bg-[#FAFAFA] border border-gray-200 text-xs font-mono tabular-nums text-[#111827] space-y-1">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[#6B7280]">
                PROOF MATH
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {Object.entries(mathObj).map(([k, v]) => (
                  <span key={k}>
                    <span className="text-[#6B7280]">{k}=</span>
                    <span>{String(v)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {(finding.evidence || []).length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
                Evidence Citations
              </div>
              <div className="flex flex-wrap gap-1.5">
                {finding.evidence.map((ev, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-[#FAFAFA] border border-gray-200 text-[11px] font-mono text-gray-700"
                  >
                    <span className="font-medium text-[#111827]">{ev.source}</span>
                    <span>{ev.record_id}</span>
                    <span className="text-gray-400">/</span>
                    <span>{ev.field}:</span>
                    <span className="font-medium text-[#111827]">{ev.value}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {finding.decisions?.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
                Decision History ({finding.decisions.length})
              </div>
              <div className="divide-y divide-gray-200 border border-gray-200 rounded-lg bg-white">
                {finding.decisions.map((d, idx) => (
                  <div
                    key={idx}
                    className="px-3 py-2 flex flex-wrap items-center justify-between gap-2 text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <StatusBadge status={d.action} />
                      <span className="font-medium text-[#111827]">{d.reviewer}</span>
                      {d.note && <span className="text-[#6B7280] truncate">{d.note}</span>}
                    </div>
                    <span className="font-mono text-[11px] text-[#6B7280]">
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
  );
}
