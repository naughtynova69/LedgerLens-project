import React, { useState } from "react";
import {
  Terminal,
  ShieldCheck,
  User,
  Clock,
  Search,
  CheckCircle2,
  XCircle,
  RotateCcw,
  HelpCircle,
} from "lucide-react";
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
    <div className="space-y-6 max-w-5xl mx-auto animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Terminal className="w-6 h-6 text-emerald-400" />
            <span>Immutable Governance & Audit Log</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Tamper-evident record of all reviewer actions, justifications, and ledger updates
          </p>
        </div>

        <div className="w-full sm:w-64">
          <div className="relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search audit trail..."
              className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>
      </div>

      {/* Log Feed */}
      {filteredLogs.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-slate-800 bg-[#0D1424] space-y-3">
          <ShieldCheck className="w-8 h-8 text-slate-500 mx-auto" />
          <h3 className="text-sm font-semibold text-white">No Audit Events Logged</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Audit entries are automatically appended whenever a reviewer approves, rejects, or flags a finding.
          </p>
        </div>
      ) : (
        <div className="bg-[#0D1424] border border-slate-800/80 rounded-2xl overflow-hidden shadow-xl">
          <div className="divide-y divide-slate-800/60">
            {filteredLogs.map((entry) => (
              <div
                key={entry.id}
                className="p-4 sm:p-5 hover:bg-slate-800/30 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="font-mono text-xs font-bold text-slate-300 flex items-center gap-1.5">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      {entry.actor}
                    </span>
                    <span className="text-slate-600">·</span>
                    <StatusBadge status={entry.action} />
                    <span className="text-slate-600">·</span>
                    <span
                      onClick={() => entry.object_id && onSelectFinding(entry.object_id)}
                      className="font-mono text-xs font-bold text-emerald-400 hover:underline cursor-pointer"
                    >
                      {entry.object_type}: {entry.object_id}
                    </span>
                  </div>

                  {entry.detail && (
                    <p className="text-xs text-slate-300 italic pl-3 border-l-2 border-slate-700">
                      "{entry.detail}"
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-500 shrink-0">
                  <Clock className="w-3.5 h-3.5" />
                  <span>{entry.ts}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
