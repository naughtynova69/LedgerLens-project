import React, { useState } from "react";
import { Terminal, ShieldCheck, User, Clock, Search } from "lucide-react";
import { StatusBadge } from "../components/StatusBadge";

export function AuditLogView({ logs, onSelectFinding }) {
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

  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Terminal className="w-5 h-5 text-[#059669]" />
            <span>Immutable Audit Log</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            Chronological tamper-evident log of ingest, extraction, R1–R5 detection, and reviewer decisions
          </p>
        </div>

        <div className="w-full sm:w-64 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search actor, action, or ID..."
            className="w-full pl-9 pr-3 py-2 bg-white border border-slate-200 rounded-lg text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-emerald-600"
          />
        </div>
      </div>

      {filteredLogs.length === 0 ? (
        <div className="p-10 text-center rounded-xl border border-slate-200 bg-white space-y-2 shadow-sm">
          <ShieldCheck className="w-8 h-8 text-slate-400 mx-auto" />
          <h3 className="text-sm font-bold text-slate-900">No Audit Events Logged</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Events are appended automatically on dataset load, extraction, rule detection, and reviewer decisions.
          </p>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm divide-y divide-slate-100">
          {filteredLogs.map((entry) => {
            const isFinding = entry.object_type === "finding" && entry.object_id;
            return (
              <div
                key={entry.id}
                className="p-4 hover:bg-slate-50 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-800 inline-flex items-center gap-1">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      {entry.actor}
                    </span>
                    <span className="text-slate-300">·</span>
                    {["open", "approve", "approved", "reject", "rejected", "recovery", "recover"].includes(
                      (entry.action || "").toLowerCase()
                    ) ? (
                      <StatusBadge status={entry.action} />
                    ) : (
                      <span className="px-2 py-0.5 rounded-md text-xs font-mono font-semibold bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE]">
                        {entry.action}
                      </span>
                    )}
                    <span className="text-slate-300">·</span>
                    <button
                      type="button"
                      disabled={!isFinding}
                      onClick={() => isFinding && onSelectFinding(entry.object_id)}
                      className={`font-mono text-xs font-bold ${
                        isFinding
                          ? "text-[#059669] hover:underline cursor-pointer"
                          : "text-slate-600 cursor-default"
                      }`}
                    >
                      {entry.object_type}: {entry.object_id}
                    </button>
                  </div>

                  {entry.detail && (
                    <p className="text-xs text-slate-600 pl-3 border-l-2 border-slate-200">
                      {entry.detail}
                    </p>
                  )}
                </div>

                <div className="inline-flex items-center gap-1.5 text-[11px] font-mono text-slate-500 shrink-0">
                  <Clock className="w-3.5 h-3.5" />
                  <span>{entry.ts}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
