import React, { useState } from "react";
import { ShieldCheck, ShieldAlert, Loader2, X } from "lucide-react";
import { api } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import { formatNumber } from "../utils/formatters";

export function AuditLogView({
  logs,
  batches,
  onSelectFinding,
  onOpenUploadModal,
  onRunDetect,
  loadingAction,
}) {
  const [search, setSearch] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifyError, setVerifyError] = useState(null);

  const handleVerifyChain = async () => {
    setVerifying(true);
    setVerifyError(null);
    try {
      const res = await api.verifyAuditChain();
      setVerifyResult(res);
    } catch (err) {
      setVerifyResult(null);
      setVerifyError(err?.message || "Failed to verify audit log integrity.");
    } finally {
      setVerifying(false);
    }
  };

  const filteredLogs = (logs || []).filter((l) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      (l.actor || "").toLowerCase().includes(q) ||
      (l.action || "").toLowerCase().includes(q) ||
      (l.object_id || "").toLowerCase().includes(q) ||
      (l.detail || "").toLowerCase().includes(q)
    );
  });

  const isStatusAction = (action) =>
    ["open", "approve", "approved", "reject", "rejected", "recovery", "recover"].includes(
      (action || "").toLowerCase()
    );

  return (
    <div className="space-y-4">
      {/* Header & Inline Pipeline Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-[15px] font-semibold text-slate-900 tracking-[-0.01em]">
            Activity &amp; Batches
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Ingested document batches and immutable chronological audit trail
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleVerifyChain}
            disabled={verifying || loadingAction}
            className="h-8 px-3 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-900 transition-colors disabled:opacity-50 inline-flex items-center gap-1.5 focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
          >
            {verifying ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-500" />
                Verifying...
              </>
            ) : (
              <>
                <ShieldCheck className="w-3.5 h-3.5 text-[#047857]" />
                Verify Ledger Integrity
              </>
            )}
          </button>
          {onOpenUploadModal && (
            <button
              type="button"
              onClick={onOpenUploadModal}
              disabled={loadingAction}
              className="h-8 px-3 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-xs font-medium text-slate-900 transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
            >
              Upload Document
            </button>
          )}
          {onRunDetect && (
            <button
              type="button"
              onClick={onRunDetect}
              disabled={loadingAction}
              className="h-8 px-3 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium transition-colors disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-slate-900 focus-visible:outline-offset-2"
            >
              Run Rules R1–R5
            </button>
          )}
        </div>
      </div>

      {/* Hash-Chain Verification Status Bar */}
      {(verifyResult || verifyError) && (
        <div
          role={verifyResult?.valid ? "status" : "alert"}
          className={`rounded-lg border px-4 py-2.5 flex items-start justify-between gap-3 ${
            verifyResult?.valid
              ? "bg-emerald-50 border-emerald-200 text-emerald-900"
              : "bg-rose-50 border-rose-200 text-rose-900"
          }`}
        >
          <div className="flex items-start gap-2.5 min-w-0">
            {verifyResult?.valid ? (
              <ShieldCheck className="w-4 h-4 text-[#047857] shrink-0 mt-0.5" />
            ) : (
              <ShieldAlert className="w-4 h-4 text-[#B91C1C] shrink-0 mt-0.5" />
            )}
            <div className="space-y-0.5 text-xs">
              <p className="font-semibold">
                {verifyResult?.valid
                  ? "Ledger Integrity Verified"
                  : verifyError
                    ? "Verification Error"
                    : "Ledger Integrity Compromised"}
              </p>
              {verifyError ? (
                <p className="text-rose-800">{verifyError}</p>
              ) : verifyResult?.valid ? (
                <p className="text-emerald-800">
                  Checked{" "}
                  <span className="font-mono tabular-nums font-medium">
                    {formatNumber(verifyResult.checked_entries)}
                  </span>{" "}
                  {verifyResult.checked_entries === 1 ? "entry" : "entries"}
                  {verifyResult.head_hash && (
                    <>
                      {" · "}Head hash:{" "}
                      <span
                        className="font-mono font-medium"
                        title={verifyResult.head_hash}
                      >
                        {verifyResult.head_hash.slice(0, 12)}...
                      </span>
                    </>
                  )}
                </p>
              ) : (
                <p className="text-rose-800">
                  Checked{" "}
                  <span className="font-mono tabular-nums font-medium">
                    {formatNumber(verifyResult.checked_entries)}
                  </span>{" "}
                  {verifyResult.checked_entries === 1 ? "entry" : "entries"}
                  {verifyResult.broken_at_id != null && (
                    <>
                      {" · "}Broken at entry{" "}
                      <span className="font-mono font-medium">
                        #{verifyResult.broken_at_id}
                      </span>
                    </>
                  )}
                  {verifyResult.reason && <> · {verifyResult.reason}</>}
                </p>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setVerifyResult(null);
              setVerifyError(null);
            }}
            aria-label="Dismiss verification status"
            className="text-current opacity-60 hover:opacity-100 p-0.5 rounded"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Compact Ingested Batches Table */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-4 py-2.5 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
            Ingested Batches
          </h2>
          <span className="text-xs font-mono tabular-nums text-slate-500">
            {batches?.length || 0} total
          </span>
        </div>

        {!batches || batches.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500">
            No document batches ingested yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px] leading-[1.4]">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="py-2 px-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                    Batch ID
                  </th>
                  <th className="py-2 px-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                    Feed
                  </th>
                  <th className="py-2 px-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 text-right">
                    Rows
                  </th>
                  <th className="py-2 px-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                    State
                  </th>
                  <th className="py-2 px-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 text-right">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {batches.map((b) => (
                  <tr key={b.batch_id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2 px-4 font-mono text-xs font-medium text-slate-900 whitespace-nowrap">
                      {b.batch_id}
                    </td>
                    <td className="py-2 px-4 font-mono text-xs text-slate-600 whitespace-nowrap">
                      {b.kind}
                    </td>
                    <td className="py-2 px-4 text-right font-mono text-xs tabular-nums text-slate-900 whitespace-nowrap">
                      {formatNumber(b.rows_detected)}
                    </td>
                    <td className="py-2 px-4 whitespace-nowrap">
                      <span className="px-1.5 py-0.5 rounded text-[11px] leading-none font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200">
                        {b.state}
                      </span>
                    </td>
                    <td className="py-2 px-4 text-right font-mono tabular-nums text-[11px] text-slate-500 whitespace-nowrap">
                      {b.created_at}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Dense Institutional Ledger Table: Immutable Audit Log */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-4 py-2.5 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
              Immutable Audit Log
            </h2>
            <span className="text-[11px] font-mono tabular-nums text-slate-500">
              ({filteredLogs.length})
            </span>
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by actor, action, ID..."
            aria-label="Filter audit log"
            className="w-full sm:w-64 h-8 px-2.5 bg-slate-50 border border-slate-300 rounded-md text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900 focus:bg-white"
          />
        </div>

        {filteredLogs.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            No audit events recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[13px] leading-[1.4]">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="py-2 px-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                    Actor
                  </th>
                  <th className="py-2 px-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                    Action
                  </th>
                  <th className="py-2 px-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                    Object
                  </th>
                  <th className="py-2 px-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500">
                    Detail
                  </th>
                  <th className="py-2 px-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-slate-500 text-right">
                    Timestamp
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {filteredLogs.map((entry) => {
                  const isFinding = entry.object_type === "finding" && entry.object_id;
                  return (
                    <tr key={entry.id} className="hover:bg-slate-50 transition-colors">
                      <td className="py-2 px-4 font-mono text-xs font-medium text-slate-900 whitespace-nowrap">
                        {entry.actor}
                      </td>
                      <td className="py-2 px-3 whitespace-nowrap">
                        {isStatusAction(entry.action) ? (
                          <StatusBadge status={entry.action} />
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[11px] leading-none font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200">
                            {entry.action}
                          </span>
                        )}
                      </td>
                      <td className="py-2 px-3 whitespace-nowrap">
                        <button
                          type="button"
                          disabled={!isFinding}
                          onClick={() => isFinding && onSelectFinding(entry.object_id)}
                          className={`font-mono text-xs ${
                            isFinding
                              ? "font-medium text-[#047857] hover:underline cursor-pointer"
                              : "text-slate-600 cursor-default"
                          }`}
                        >
                          {entry.object_type}: {entry.object_id}
                        </button>
                      </td>
                      <td
                        className="py-2 px-3 text-xs text-slate-600 max-w-md truncate"
                        title={entry.detail || ""}
                      >
                        {entry.detail || "—"}
                      </td>
                      <td className="py-2 px-4 text-right font-mono tabular-nums text-[11px] text-slate-500 whitespace-nowrap">
                        {entry.ts}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
