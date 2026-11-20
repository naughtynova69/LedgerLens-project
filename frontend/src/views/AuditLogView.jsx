import React, { useState } from "react";
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
    <div className="space-y-6">
      {/* Header & Inline Pipeline Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-[#111827] tracking-tight">
            Activity &amp; Batches
          </h1>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Ingested document batches and immutable chronological audit trail
          </p>
        </div>

        <div className="flex items-center gap-2">
          {onOpenUploadModal && (
            <button
              type="button"
              onClick={onOpenUploadModal}
              disabled={loadingAction}
              className="px-3 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-xs font-medium text-[#111827] transition-colors disabled:opacity-50"
            >
              Upload Document
            </button>
          )}
          {onRunDetect && (
            <button
              type="button"
              onClick={onRunDetect}
              disabled={loadingAction}
              className="px-3 py-1.5 rounded-lg bg-[#111827] hover:bg-gray-800 text-white text-xs font-medium transition-colors disabled:opacity-50"
            >
              Run Rules R1–R5
            </button>
          )}
        </div>
      </div>

      {/* Compact Ingested Batches Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#6B7280]">
            Ingested Batches
          </h2>
          <span className="text-xs font-mono tabular-nums text-[#6B7280]">
            {batches?.length || 0} total
          </span>
        </div>

        {!batches || batches.length === 0 ? (
          <div className="p-6 text-center text-xs text-[#6B7280]">
            No document batches ingested yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#FAFAFA] border-b border-gray-200 text-[#6B7280]">
                <tr>
                  <th className="py-2 px-4 font-medium">Batch ID</th>
                  <th className="py-2 px-4 font-medium">Feed</th>
                  <th className="py-2 px-4 font-medium text-right">Rows</th>
                  <th className="py-2 px-4 font-medium">State</th>
                  <th className="py-2 px-4 font-medium text-right">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {batches.map((b) => (
                  <tr key={b.batch_id} className="hover:bg-gray-50/70">
                    <td className="py-2.5 px-4 font-mono font-medium text-[#111827]">
                      {b.batch_id}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-[#6B7280]">{b.kind}</td>
                    <td className="py-2.5 px-4 text-right font-mono tabular-nums text-[#111827]">
                      {formatNumber(b.rows_detected)}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-50 text-gray-700 border border-gray-200">
                        {b.state}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono text-[11px] text-[#6B7280]">
                      {b.created_at}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Immutable Audit Log Timeline */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-[#6B7280]">
            Immutable Audit Log
          </h2>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by actor, action, ID..."
            aria-label="Filter audit log"
            className="w-full sm:w-64 px-2.5 py-1 bg-[#FAFAFA] border border-gray-200 rounded-md text-xs text-[#111827] placeholder-gray-400 focus:outline-none focus:border-gray-400 focus:bg-white"
          />
        </div>

        {filteredLogs.length === 0 ? (
          <div className="p-8 text-center text-xs text-[#6B7280]">
            No audit events recorded yet.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {filteredLogs.map((entry) => {
              const isFinding = entry.object_type === "finding" && entry.object_id;
              return (
                <div
                  key={entry.id}
                  className="px-4 py-3 hover:bg-gray-50/70 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                >
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-mono font-medium text-[#111827]">
                        {entry.actor}
                      </span>
                      <span className="text-gray-300">·</span>
                      {isStatusAction(entry.action) ? (
                        <StatusBadge status={entry.action} />
                      ) : (
                        <span className="px-2 py-0.5 rounded-md text-[11px] font-mono font-medium bg-gray-50 text-gray-700 border border-gray-200">
                          {entry.action}
                        </span>
                      )}
                      <span className="text-gray-300">·</span>
                      <button
                        type="button"
                        disabled={!isFinding}
                        onClick={() => isFinding && onSelectFinding(entry.object_id)}
                        className={`font-mono text-xs ${
                          isFinding
                            ? "font-medium text-[#047857] hover:underline cursor-pointer"
                            : "text-[#6B7280] cursor-default"
                        }`}
                      >
                        {entry.object_type}: {entry.object_id}
                      </button>
                    </div>

                    {entry.detail && (
                      <p className="text-xs text-[#6B7280] truncate" title={entry.detail}>
                        {entry.detail}
                      </p>
                    )}
                  </div>

                  <span className="font-mono text-[11px] text-[#6B7280] shrink-0">
                    {entry.ts}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
