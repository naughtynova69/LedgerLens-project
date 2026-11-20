import React, { useState, useMemo } from "react";
import {
  Search,
  ShieldAlert,
  Database,
  CheckCircle2,
} from "lucide-react";
import { RuleBadge } from "../components/RuleBadge";
import { StatusBadge } from "../components/StatusBadge";
import { ProofTrailInspector } from "../components/ProofTrailInspector";
import { formatCurrency, formatConfidence } from "../utils/formatters";

export function FindingsView({
  findings,
  selectedFindingId,
  selectedFindingDetail,
  onSelectFinding,
  onMakeDecision,
  isSubmittingDecision,
  onSeedDemo,
  loadingAction,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [ruleFilter, setRuleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const rulesList = [
    { id: "all", label: "All" },
    { id: "R1", label: "R1 Duplicate" },
    { id: "R2", label: "R2 Price" },
    { id: "R3", label: "R3 PO" },
    { id: "R4", label: "R4 FX/Tax" },
    { id: "R5", label: "R5 Cancelled" },
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
    { id: "open", label: "Open" },
    { id: "approved", label: "Approved" },
    { id: "rejected", label: "Rejected" },
    { id: "recovery", label: "Recovered" },
  ];

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
      result = result.filter((f) => f.severity.toLowerCase() === severityFilter);
    }

    if (ruleFilter !== "all") {
      result = result.filter((f) => f.rule_id === ruleFilter);
    }

    if (statusFilter !== "all") {
      result = result.filter((f) => f.status.toLowerCase() === statusFilter);
    }

    return result.sort((a, b) => b.amount_at_risk - a.amount_at_risk);
  }, [findings, searchQuery, severityFilter, ruleFilter, statusFilter]);

  const totalFilteredAmount = useMemo(
    () => filteredFindings.reduce((acc, f) => acc + (f.amount_at_risk || 0), 0),
    [filteredFindings]
  );

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-[#DC2626]" />
            <span>Exception Queue & Split-View Proof Trail Explorer</span>
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            Click any finding on the left to inspect its 3-way Invoice vs. Contract vs. PO proof trail on the right.
          </p>
        </div>

        <div className="px-4 py-2 rounded-xl bg-white border border-slate-200 text-right shrink-0 shadow-sm">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 block">
            Filtered Exposure
          </span>
          <span className="text-lg font-bold font-mono tabular-nums text-[#DC2626]">
            {formatCurrency(totalFilteredAmount)}
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-3 shadow-sm">
        <div className="flex flex-col md:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search finding ID, vendor ID, invoice #, or keyword..."
              className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:border-emerald-600 focus:bg-white"
            />
          </div>

          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            aria-label="Filter by severity"
            className="w-full md:w-44 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs sm:text-sm text-slate-800 focus:outline-none focus:border-emerald-600"
          >
            {severitiesList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
            className="w-full md:w-44 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs sm:text-sm text-slate-800 focus:outline-none focus:border-emerald-600"
          >
            {statusesList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        {/* Rule Chips */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-500 font-semibold mr-1">Rule:</span>
          {rulesList.map((r) => {
            const active = ruleFilter === r.id;
            return (
              <button
                key={r.id}
                onClick={() => setRuleFilter(r.id)}
                className={`px-3 py-1 rounded-lg font-semibold transition-colors border ${
                  active
                    ? "bg-slate-900 text-white border-slate-900"
                    : "bg-slate-50 text-slate-600 hover:bg-slate-100 border-slate-200"
                }`}
              >
                {r.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Empty State or Split-View */}
      {filteredFindings.length === 0 ? (
        <div className="p-12 text-center rounded-xl border border-slate-200 bg-white space-y-3 shadow-sm">
          <div className="w-11 h-11 rounded-full bg-slate-100 text-slate-500 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <h3 className="text-base font-bold text-slate-900">No Matching Findings</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {findings?.length === 0
              ? "Load the sample dataset or upload CSV/PDF documents to run deterministic rules R1–R5."
              : "Adjust your rule, severity, or status filters."}
          </p>
          {findings?.length === 0 && (
            <button
              onClick={onSeedDemo}
              disabled={loadingAction}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#059669] hover:bg-[#047857] text-white font-semibold text-xs"
            >
              <Database className="w-4 h-4" />
              <span>Load Demo Dataset (6 Planted Anomalies)</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left: Filterable Tabular Findings Queue */}
          <div className="lg:col-span-5 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[10px] font-bold tracking-wider">
                  <tr>
                    <th className="py-3 px-3">Finding / Rule</th>
                    <th className="py-3 px-2">Vendor / Invoice #</th>
                    <th className="py-3 px-2 text-right">Amount at Risk</th>
                    <th className="py-3 px-3 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredFindings.map((finding) => {
                    const isSelected = selectedFindingId === finding.finding_id;
                    const refs = finding.entity_refs || {};
                    const invList = refs.invoice_numbers || [];
                    return (
                      <tr
                        key={finding.finding_id}
                        onClick={() => onSelectFinding(finding.finding_id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-emerald-50/70 border-l-4 border-l-[#059669]"
                            : "hover:bg-slate-50"
                        }`}
                      >
                        <td className="py-3 px-3 whitespace-nowrap">
                          <div className="font-mono font-bold text-slate-900">
                            {finding.finding_id}
                          </div>
                          <div className="mt-1">
                            <RuleBadge ruleId={finding.rule_id} />
                          </div>
                        </td>

                        <td className="py-3 px-2 min-w-[130px]">
                          <div className="font-semibold text-slate-900 truncate max-w-[160px]" title={finding.title}>
                            {refs.vendor_id || "Vendor"}
                          </div>
                          <div className="font-mono text-[11px] text-slate-500 truncate max-w-[160px]">
                            {invList.join(", ") || "—"}
                          </div>
                        </td>

                        <td className="py-3 px-2 text-right whitespace-nowrap">
                          <div className="font-mono tabular-nums font-bold text-[#DC2626]">
                            {formatCurrency(finding.amount_at_risk, finding.currency)}
                          </div>
                          <div className="font-mono tabular-nums text-[10px] text-slate-500">
                            Conf: {formatConfidence(finding.confidence)}
                          </div>
                        </td>

                        <td className="py-3 px-3 text-right whitespace-nowrap">
                          <StatusBadge status={finding.status} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-2.5 border-t border-slate-100 bg-slate-50 text-[11px] text-slate-500 flex items-center justify-between font-mono">
              <span>{filteredFindings.length} of {findings.length} findings</span>
              <span>Sorted: Risk DESC</span>
            </div>
          </div>

          {/* Right: Split-View Proof Trail Inspector */}
          <div className="lg:col-span-7">
            <ProofTrailInspector
              finding={selectedFindingDetail}
              onMakeDecision={onMakeDecision}
              isSubmitting={isSubmittingDecision}
            />
          </div>
        </div>
      )}
    </div>
  );
}
