import React, { useState, useMemo } from "react";
import {
  Search,
  Filter,
  ArrowUpDown,
  ShieldAlert,
  ChevronRight,
  Database,
  CheckCircle2,
} from "lucide-react";
import { SeverityBadge } from "../components/SeverityBadge";
import { RuleBadge } from "../components/RuleBadge";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatConfidence } from "../utils/formatters";

export function FindingsView({
  findings,
  onSelectFinding,
  onSeedDemo,
  loadingAction,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [ruleFilter, setRuleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("amount_desc");

  const rulesList = [
    { id: "all", label: "All Rules" },
    { id: "R1", label: "R1 Duplicate" },
    { id: "R2", label: "R2 Contract Price" },
    { id: "R3", label: "R3 PO Overbilling" },
    { id: "R4", label: "R4 Currency / Tax" },
    { id: "R5", label: "R5 Cancelled Service" },
  ];

  const severitiesList = [
    { id: "all", label: "All Severities" },
    { id: "critical", label: "Critical" },
    { id: "high", label: "High" },
    { id: "medium", label: "Medium" },
    { id: "low", label: "Low" },
  ];

  const statusesList = [
    { id: "all", label: "All Statuses" },
    { id: "open", label: "Needs Review" },
    { id: "approved", label: "Approved" },
    { id: "rejected", label: "Blocked" },
    { id: "recovery", label: "In Recovery" },
  ];

  // Filtered & Sorted list
  const filteredFindings = useMemo(() => {
    let result = [...(findings || [])];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (f) =>
          f.finding_id.toLowerCase().includes(q) ||
          f.title.toLowerCase().includes(q) ||
          f.summary.toLowerCase().includes(q) ||
          JSON.stringify(f.entity_refs || {}).toLowerCase().includes(q)
      );
    }

    if (severityFilter !== "all") {
      result = result.filter((f) => f.severity.toLowerCase() === severityFilter.toLowerCase());
    }

    if (ruleFilter !== "all") {
      result = result.filter((f) => f.rule_id === ruleFilter);
    }

    if (statusFilter !== "all") {
      result = result.filter((f) => f.status.toLowerCase() === statusFilter.toLowerCase());
    }

    result.sort((a, b) => {
      if (sortBy === "amount_desc") return b.amount_at_risk - a.amount_at_risk;
      if (sortBy === "amount_asc") return a.amount_at_risk - b.amount_at_risk;
      if (sortBy === "confidence_desc") return b.confidence - a.confidence;
      if (sortBy === "rule_asc") return a.rule_id.localeCompare(b.rule_id);
      return 0;
    });

    return result;
  }, [findings, searchQuery, severityFilter, ruleFilter, statusFilter, sortBy]);

  const totalFilteredAmount = useMemo(() => {
    return filteredFindings.reduce((acc, f) => acc + (f.amount_at_risk || 0), 0);
  }, [filteredFindings]);

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Header with Title and Total */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <ShieldAlert className="w-6 h-6 text-rose-400" />
            <span>Spend Exception Queue</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Prioritized disbursement risks with explainable evidence trails
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-right">
            <span className="text-[11px] text-slate-400 block">Filtered Exposure:</span>
            <span className="text-lg font-bold font-mono text-rose-400">
              {formatCurrency(totalFilteredAmount)}
            </span>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-2xl bg-[#0D1424] border border-slate-800/80 space-y-4">
        <div className="flex flex-col md:flex-row items-center gap-3">
          {/* Search Box */}
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by finding ID, invoice number, vendor, or keyword..."
              className="w-full pl-10 pr-4 py-2 bg-slate-900/80 border border-slate-800 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 transition-colors"
            />
          </div>

          {/* Severity Filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="w-full md:w-44 px-3 py-2 bg-slate-900/80 border border-slate-800 rounded-xl text-xs sm:text-sm text-slate-200 focus:outline-none focus:border-emerald-500/50"
          >
            {severitiesList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="w-full md:w-44 px-3 py-2 bg-slate-900/80 border border-slate-800 rounded-xl text-xs sm:text-sm text-slate-200 focus:outline-none focus:border-emerald-500/50"
          >
            {statusesList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>

          {/* Sort By */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="w-full md:w-48 px-3 py-2 bg-slate-900/80 border border-slate-800 rounded-xl text-xs sm:text-sm text-slate-200 focus:outline-none focus:border-emerald-500/50"
          >
            <option value="amount_desc">Amount (Highest First)</option>
            <option value="amount_asc">Amount (Lowest First)</option>
            <option value="confidence_desc">Highest Confidence</option>
            <option value="rule_asc">Rule Category</option>
          </select>
        </div>

        {/* Rule Filter Chips */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar text-xs">
          <span className="text-slate-400 font-medium whitespace-nowrap mr-1">Rule:</span>
          {rulesList.map((r) => {
            const active = ruleFilter === r.id;
            return (
              <button
                key={r.id}
                onClick={() => setRuleFilter(r.id)}
                className={`px-3 py-1 rounded-lg font-medium whitespace-nowrap transition-all ${
                  active
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    : "bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
              >
                {r.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Findings Table */}
      {filteredFindings.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-slate-800 bg-[#0D1424] space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-white">No Matching Exceptions Found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            {findings?.length === 0
              ? "The spend audit queue has no findings registered yet."
              : "Try adjusting your search keywords or filter criteria."}
          </p>
          {findings?.length === 0 && (
            <button
              onClick={onSeedDemo}
              disabled={loadingAction}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs transition-all"
            >
              <Database className="w-4 h-4" />
              <span>Load 6 Demo Anomalies</span>
            </button>
          )}
        </div>
      ) : (
        <div className="bg-[#0D1424] border border-slate-800/80 rounded-2xl overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead className="bg-[#111A2E]/80 border-b border-slate-800 text-slate-400 uppercase text-[11px] font-semibold tracking-wider">
                <tr>
                  <th className="py-3.5 px-4 sm:px-6">Finding ID & Rule</th>
                  <th className="py-3.5 px-4">Title & Context</th>
                  <th className="py-3.5 px-4 text-center">Severity</th>
                  <th className="py-3.5 px-4 text-right">Amount at Risk</th>
                  <th className="py-3.5 px-4 text-center">Confidence</th>
                  <th className="py-3.5 px-4 text-center">Status</th>
                  <th className="py-3.5 px-4 sm:px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredFindings.map((finding) => (
                  <tr
                    key={finding.finding_id}
                    onClick={() => onSelectFinding(finding.finding_id)}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer group"
                  >
                    {/* Finding ID & Rule */}
                    <td className="py-4 px-4 sm:px-6 whitespace-nowrap">
                      <div className="space-y-1">
                        <span className="font-mono font-semibold text-white group-hover:text-emerald-300 transition-colors">
                          {finding.finding_id}
                        </span>
                        <div>
                          <RuleBadge ruleId={finding.rule_id} />
                        </div>
                      </div>
                    </td>

                    {/* Title & Summary */}
                    <td className="py-4 px-4 max-w-md">
                      <div className="space-y-1">
                        <p className="font-semibold text-slate-200 group-hover:text-white transition-colors truncate">
                          {finding.title}
                        </p>
                        <p className="text-xs text-slate-400 line-clamp-1">
                          {finding.summary}
                        </p>
                      </div>
                    </td>

                    {/* Severity */}
                    <td className="py-4 px-4 text-center whitespace-nowrap">
                      <SeverityBadge severity={finding.severity} />
                    </td>

                    {/* Amount at Risk */}
                    <td className="py-4 px-4 text-right whitespace-nowrap">
                      <span className="font-mono font-bold text-sm sm:text-base text-rose-400">
                        {formatCurrency(finding.amount_at_risk, finding.currency)}
                      </span>
                    </td>

                    {/* Confidence */}
                    <td className="py-4 px-4 text-center whitespace-nowrap font-mono text-xs text-slate-300">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                        {formatConfidence(finding.confidence)}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="py-4 px-4 text-center whitespace-nowrap">
                      <StatusBadge status={finding.status} />
                    </td>

                    {/* Action Button */}
                    <td className="py-4 px-4 sm:px-6 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectFinding(finding.finding_id);
                        }}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-emerald-500 hover:text-slate-950 text-slate-300 font-medium text-xs border border-slate-700 hover:border-emerald-400 transition-all"
                      >
                        <span>Inspect</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 border-t border-slate-800 bg-[#0B1220]/60 flex items-center justify-between text-xs text-slate-400">
            <span>Showing {filteredFindings.length} of {findings?.length || 0} findings</span>
            <span className="font-mono">Sorted by {sortBy.replace("_", " ").toUpperCase()}</span>
          </div>
        </div>
      )}
    </div>
  );
}
