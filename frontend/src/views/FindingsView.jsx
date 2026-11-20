import React, { useState, useMemo, useEffect } from "react";
import { RuleBadge } from "../components/RuleBadge";
import { StatusBadge } from "../components/StatusBadge";
import { ProofTrailInspector } from "../components/ProofTrailInspector";
import { GraphStatsCard } from "../components/GraphStatsCard";
import { formatCurrency, formatConfidence } from "../utils/formatters";

export function FindingsView({
  findings,
  stats,
  executiveAnalytics,
  selectedFindingId,
  selectedFindingDetail,
  onSelectFinding,
  onMakeDecision,
  onBulkDecision,
  isSubmittingDecision,
  onSeedDemo,
  loadingAction,
  onToast,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [ruleFilter, setRuleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [checkedIds, setCheckedIds] = useState([]);

  const rulesList = [
    { id: "all", label: "All Rules" },
    { id: "R1", label: "R1 Duplicate" },
    { id: "R2", label: "R2 Price" },
    { id: "R3", label: "R3 PO" },
    { id: "R4", label: "R4 FX/Tax" },
    { id: "R5", label: "R5 Cancelled" },
    { id: "R6", label: "R6 Split-PO" },
    { id: "R7", label: "R7 GRN" },
    { id: "R8", label: "R8 Graph-Dup" },
    { id: "R9", label: "R9 Collusion" },
    { id: "R10", label: "R10 Lineage" },
  ];

  const statusTabs = [
    { id: "all", label: "All" },
    { id: "open", label: "Open" },
    { id: "recovered", label: "Recovered" },
  ];

  const filteredFindings = useMemo(() => {
    let result = [...(findings || [])];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (f) =>
          f.finding_id.toLowerCase().includes(q) ||
          f.title.toLowerCase().includes(q) ||
          (f.summary || "").toLowerCase().includes(q) ||
          JSON.stringify(f.entity_refs || {}).toLowerCase().includes(q)
      );
    }

    if (ruleFilter !== "all") {
      result = result.filter((f) => f.rule_id === ruleFilter);
    }

    if (statusFilter === "open") {
      result = result.filter((f) => (f.status || "").toLowerCase() === "open");
    } else if (statusFilter === "recovered") {
      result = result.filter((f) =>
        ["recovery", "recovered", "rejected"].includes((f.status || "").toLowerCase())
      );
    }

    return result.sort((a, b) => b.amount_at_risk - a.amount_at_risk);
  }, [findings, searchQuery, ruleFilter, statusFilter]);

  useEffect(() => {
    const validIds = new Set((findings || []).map((f) => f.finding_id));
    setCheckedIds((prev) => prev.filter((id) => validIds.has(id)));
  }, [findings]);

  const allFilteredChecked =
    filteredFindings.length > 0 &&
    filteredFindings.every((f) => checkedIds.includes(f.finding_id));

  const toggleAllFiltered = () => {
    if (allFilteredChecked) {
      const filteredSet = new Set(filteredFindings.map((f) => f.finding_id));
      setCheckedIds((prev) => prev.filter((id) => !filteredSet.has(id)));
    } else {
      const merged = new Set([
        ...checkedIds,
        ...filteredFindings.map((f) => f.finding_id),
      ]);
      setCheckedIds(Array.from(merged));
    }
  };

  const toggleOne = (findingId) => {
    setCheckedIds((prev) =>
      prev.includes(findingId)
        ? prev.filter((id) => id !== findingId)
        : [...prev, findingId]
    );
  };

  const handleBulkAction = async (action) => {
    if (checkedIds.length === 0 || !onBulkDecision) return;
    await onBulkDecision(checkedIds, action);
    setCheckedIds([]);
  };

  const atRiskInr =
    executiveAnalytics?.total_at_risk_inr ?? stats?.total_at_risk ?? 0;
  const openCount = stats?.by_status?.open ?? 0;
  const recoveredInr =
    executiveAnalytics?.recovered_inr ?? stats?.recovered_amount ?? 0;
  const auditedSpendInr =
    executiveAnalytics?.total_audited_spend_inr ?? stats?.total_audited_spend ?? 0;

  return (
    <div className="space-y-4">
      {/* 4-Metric Executive Strip */}
      <div className="bg-white border border-gray-200 rounded-lg grid grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-gray-200">
        <div className="px-4 py-3.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            At Risk (INR Eq.)
          </div>
          <div className="text-lg font-semibold font-mono tabular-nums text-[#B91C1C] mt-1">
            {formatCurrency(atRiskInr, "INR")}
          </div>
        </div>

        <div className="px-4 py-3.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            Open Items
          </div>
          <div className="text-lg font-semibold font-mono tabular-nums text-[#111827] mt-1">
            {openCount}
          </div>
        </div>

        <div className="px-4 py-3.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            Recovered
          </div>
          <div className="text-lg font-semibold font-mono tabular-nums text-[#047857] mt-1">
            {formatCurrency(recoveredInr, "INR")}
          </div>
        </div>

        <div className="px-4 py-3.5">
          <div className="text-[11px] font-medium uppercase tracking-wider text-[#6B7280]">
            Audited Spend
          </div>
          <div className="text-lg font-semibold font-mono tabular-nums text-[#111827] mt-1">
            {formatCurrency(auditedSpendInr, "INR")}
          </div>
        </div>
      </div>

      {/* Embedded knowledge-graph KPI strip (LadybugDB) */}
      <GraphStatsCard onToast={onToast} />

      {/* Single-Row Filter Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
            {statusTabs.map((tab) => {
              const active = statusFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setStatusFilter(tab.id)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    active
                      ? "bg-gray-100 text-[#111827]"
                      : "text-[#6B7280] hover:text-[#111827]"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          <select
            value={ruleFilter}
            onChange={(e) => setRuleFilter(e.target.value)}
            aria-label="Filter by rule"
            className="px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg text-xs text-[#111827] focus:outline-none focus:border-gray-400"
          >
            {rulesList.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search vendor, invoice #, finding..."
          aria-label="Search exceptions"
          className="w-full sm:w-64 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs text-[#111827] placeholder-gray-400 focus:outline-none focus:border-gray-400"
        />
      </div>

      {/* Inline Bulk Triage Bar */}
      {checkedIds.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
          <span className="text-xs font-medium text-[#111827] font-mono tabular-nums">
            {checkedIds.length} selected
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => handleBulkAction("recovery")}
              disabled={isSubmittingDecision}
              className="px-3 py-1 rounded-lg text-xs font-medium bg-red-50/80 text-red-700 border border-red-200 hover:bg-red-100/70 transition-colors disabled:opacity-50"
            >
              Hold / Recover Selected
            </button>
            <button
              type="button"
              onClick={() => handleBulkAction("approve")}
              disabled={isSubmittingDecision}
              className="px-3 py-1 rounded-lg text-xs font-medium bg-emerald-50/80 text-emerald-700 border border-emerald-200 hover:bg-emerald-100/70 transition-colors disabled:opacity-50"
            >
              Approve Selected
            </button>
            <button
              type="button"
              onClick={() => setCheckedIds([])}
              className="px-2.5 py-1 rounded-lg text-xs font-medium text-[#6B7280] hover:text-[#111827] border border-gray-200 bg-white hover:bg-gray-50 transition-colors"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Empty State or Split-View */}
      {filteredFindings.length === 0 ? (
        <div className="p-12 text-center rounded-lg border border-gray-200 bg-white space-y-3">
          <h3 className="text-sm font-semibold text-[#111827]">No matching exceptions</h3>
          <p className="text-xs text-[#6B7280] max-w-sm mx-auto">
            {findings?.length === 0
              ? "Load the demo dataset or upload CSV/PDF documents to run deterministic rules R1–R5."
              : "Adjust your status, rule, or search filters."}
          </p>
          {findings?.length === 0 && (
            <button
              type="button"
              onClick={onSeedDemo}
              disabled={loadingAction}
              className="px-3.5 py-1.5 rounded-lg bg-[#111827] hover:bg-gray-800 text-white font-medium text-xs transition-colors disabled:opacity-50"
            >
              Load Demo Dataset
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          {/* Left: Clean 5-Column Ledger Table */}
          <div className="lg:col-span-5 bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAFAFA] border-b border-gray-200 text-[#6B7280]">
                  <tr>
                    <th className="py-2.5 pl-3 pr-1 w-8">
                      <input
                        type="checkbox"
                        checked={allFilteredChecked}
                        onChange={toggleAllFiltered}
                        aria-label="Select all visible findings"
                        className="rounded border-gray-300 text-[#111827] focus:ring-0"
                      />
                    </th>
                    <th className="py-2.5 px-2 font-medium">Vendor / Rule</th>
                    <th className="py-2.5 px-2 font-medium">Invoice #</th>
                    <th className="py-2.5 px-2 font-medium text-right">Amount</th>
                    <th className="py-2.5 pl-2 pr-3 font-medium text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {filteredFindings.map((finding) => {
                    const isSelected = selectedFindingId === finding.finding_id;
                    const isChecked = checkedIds.includes(finding.finding_id);
                    const refs = finding.entity_refs || {};
                    const invList = refs.invoice_numbers || [];
                    return (
                      <tr
                        key={finding.finding_id}
                        onClick={() => onSelectFinding(finding.finding_id)}
                        className={`cursor-pointer transition-colors ${
                          isSelected ? "bg-gray-50" : "hover:bg-gray-50/70"
                        }`}
                      >
                        <td
                          className="py-2.5 pl-3 pr-1 align-top"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleOne(finding.finding_id)}
                            aria-label={`Select ${finding.finding_id}`}
                            className="mt-0.5 rounded border-gray-300 text-[#111827] focus:ring-0"
                          />
                        </td>

                        <td className="py-2.5 px-2 align-top">
                          <div
                            className="font-medium text-[#111827] truncate max-w-[130px]"
                            title={finding.title}
                          >
                            {refs.vendor_id || "Vendor"}
                          </div>
                          <div className="mt-1">
                            <RuleBadge ruleId={finding.rule_id} />
                          </div>
                        </td>

                        <td className="py-2.5 px-2 align-top">
                          <div
                            className="font-mono text-[#111827] truncate max-w-[115px]"
                            title={invList.join(", ")}
                          >
                            {invList[0] || "—"}
                          </div>
                          <div className="font-mono text-[11px] text-[#6B7280]">
                            {finding.finding_id}
                          </div>
                        </td>

                        <td className="py-2.5 px-2 text-right whitespace-nowrap align-top">
                          <div className="font-mono tabular-nums font-medium text-[#B91C1C]">
                            {formatCurrency(finding.amount_at_risk, finding.currency)}
                          </div>
                          <div className="font-mono tabular-nums text-[11px] text-[#6B7280]">
                            {formatConfidence(finding.confidence)}
                          </div>
                        </td>

                        <td className="py-2.5 pl-2 pr-3 text-right whitespace-nowrap align-top">
                          <StatusBadge status={finding.status} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-3.5 py-2 border-t border-gray-200 bg-[#FAFAFA] text-[11px] text-[#6B7280] flex items-center justify-between font-mono tabular-nums">
              <span>
                {filteredFindings.length} of {findings.length} exceptions
              </span>
              <span>Sorted by exposure</span>
            </div>
          </div>

          {/* Right: Calm Decision Pane */}
          <div className="lg:col-span-7">
            <ProofTrailInspector
              finding={selectedFindingDetail}
              onMakeDecision={onMakeDecision}
              isSubmitting={isSubmittingDecision}
              onToast={onToast}
            />
          </div>
        </div>
      )}
    </div>
  );
}
