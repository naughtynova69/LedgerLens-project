import React, { useState, useMemo, useEffect, useRef } from "react";
import { Search, X, Download, PlayCircle, ShieldCheck, Loader2 } from "lucide-react";
import { api } from "../api";
import { RuleBadge } from "../components/RuleBadge";
import { StatusBadge } from "../components/StatusBadge";
import { ProofTrailInspector } from "../components/ProofTrailInspector";
import { formatCurrency } from "../utils/formatters";
import { useAccountMemory } from "../context/AccountMemoryContext";

const SEVERITY_DOT = {
  critical: "bg-[#B91C1C]",
  high: "bg-[#D97706]",
  medium: "bg-slate-500",
  low: "bg-slate-400",
};

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
  onOpenDemoGuide,
  onRunPayrunSweep,
  runningSweep = false,
  loadingAction,
  onToast,
}) {
  const { filters, setFilters, resetFilters, reviewerLabel } = useAccountMemory();
  const searchQuery = filters.searchQuery || "";
  const ruleFilter = filters.ruleFilter || "all";
  const statusFilter = filters.statusFilter || "all";

  const setSearchQuery = (val) => setFilters({ searchQuery: val });
  const setRuleFilter = (val) => setFilters({ ruleFilter: val });
  const setStatusFilter = (val) => setFilters({ statusFilter: val });

  const [checkedIds, setCheckedIds] = useState([]);
  const searchInputRef = useRef(null);

  const rulesList = [
    { id: "all", label: "All Issues" },
    { id: "R1", label: "Duplicate Bill" },
    { id: "R2", label: "Price Overcharge" },
    { id: "R3", label: "PO Mismatch" },
    { id: "R4", label: "Tax / Currency" },
    { id: "R5", label: "Cancelled Service" },
    { id: "R6", label: "Split Order" },
    { id: "R7", label: "Delivery Mismatch" },
    { id: "R8", label: "Linked Vendors" },
    { id: "R9", label: "Conflict of Interest" },
    { id: "R10", label: "Missing Credit" },
  ];

  const statusTabs = [
    { id: "all", label: "All" },
    { id: "open", label: "Needs Review" },
    { id: "recovered", label: "Saved" },
  ];

  const ruleCounts = useMemo(() => {
    const counts = {};
    for (const f of findings || []) {
      counts[f.rule_id] = (counts[f.rule_id] || 0) + 1;
    }
    return counts;
  }, [findings]);

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

  // Keyboard-first triage: j/k or ↑/↓ navigate, / focus search, a/r recover, d dispute, Esc clear
  useEffect(() => {
    const onKeyDown = (e) => {
      const tag = (e.target?.tagName || "").toLowerCase();
      const isEditing =
        tag === "input" || tag === "textarea" || tag === "select" || e.target?.isContentEditable;

      if (e.key === "Escape") {
        if (isEditing && e.target === searchInputRef.current) {
          e.target.blur();
        }
        setSearchQuery("");
        setCheckedIds([]);
        return;
      }

      if (isEditing || e.metaKey || e.ctrlKey || e.altKey) {
        return;
      }

      if (e.key === "/") {
        e.preventDefault();
        searchInputRef.current?.focus();
        return;
      }

      if (e.key === "j" || e.key === "ArrowDown") {
        if (!filteredFindings.length) return;
        e.preventDefault();
        const idx = filteredFindings.findIndex((f) => f.finding_id === selectedFindingId);
        const nextIdx = idx < 0 ? 0 : Math.min(idx + 1, filteredFindings.length - 1);
        onSelectFinding(filteredFindings[nextIdx].finding_id);
        return;
      }

      if (e.key === "k" || e.key === "ArrowUp") {
        if (!filteredFindings.length) return;
        e.preventDefault();
        const idx = filteredFindings.findIndex((f) => f.finding_id === selectedFindingId);
        const prevIdx = idx <= 0 ? 0 : idx - 1;
        onSelectFinding(filteredFindings[prevIdx].finding_id);
        return;
      }

      const activeId = selectedFindingDetail?.finding_id || selectedFindingId;
      if (!activeId || isSubmittingDecision || !onMakeDecision) return;

      if (e.key === "a" || e.key === "r") {
        e.preventDefault();
        onMakeDecision(
          activeId,
          "recovery",
          reviewerLabel,
          "Payment held and recovery initiated via AP workstation."
        );
      } else if (e.key === "d") {
        e.preventDefault();
        onMakeDecision(
          activeId,
          "reject",
          reviewerLabel,
          "Disputed with vendor pending credit note or revised invoice."
        );
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    filteredFindings,
    selectedFindingId,
    selectedFindingDetail,
    onSelectFinding,
    onMakeDecision,
    isSubmittingDecision,
    reviewerLabel,
  ]);

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
    <div className="space-y-3">
      {/* 4-Metric Financial KPI Strip */}
      <div className="bg-white border border-[#E2E8F0] rounded-md grid grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-[#E2E8F0]">
        <div className="px-4 py-3">
          <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Money at Risk
          </div>
          <div className="text-lg font-semibold font-mono tabular-nums text-[#B91C1C] mt-0.5">
            {formatCurrency(atRiskInr, "INR")}
          </div>
        </div>

        <div className="px-4 py-3">
          <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Needs Review
          </div>
          <div className="text-lg font-semibold font-mono tabular-nums text-slate-900 mt-0.5">
            {openCount}
          </div>
        </div>

        <div className="px-4 py-3">
          <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Money Saved
          </div>
          <div className="text-lg font-semibold font-mono tabular-nums text-[#047857] mt-0.5">
            {formatCurrency(recoveredInr, "INR")}
          </div>
        </div>

        <div className="px-4 py-3">
          <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
            Total Checked
          </div>
          <div className="text-lg font-semibold font-mono tabular-nums text-slate-900 mt-0.5">
            {formatCurrency(auditedSpendInr, "INR")}
          </div>
        </div>
      </div>

      {/* 40px Single-Row Triage Toolbar */}
      <div className="min-h-[40px] flex flex-wrap items-center justify-between gap-2 bg-white border border-[#E2E8F0] rounded-md px-2.5 py-1.5">
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Segmented Control */}
          <div className="inline-flex rounded border border-[#E2E8F0] bg-[#F8FAFC] p-0.5">
            {statusTabs.map((tab) => {
              const active = statusFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setStatusFilter(tab.id)}
                  className={`px-2.5 py-1 rounded-sm text-xs font-medium transition-colors ${
                    active
                      ? "bg-white text-slate-900 shadow-sm border border-[#E2E8F0]"
                      : "text-slate-500 hover:text-slate-900 border border-transparent"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Rule Filter Dropdown */}
          <select
            value={ruleFilter}
            onChange={(e) => setRuleFilter(e.target.value)}
            aria-label="Filter by rule"
            className="h-7 px-2 bg-white border border-[#E2E8F0] rounded text-xs text-slate-900 focus:outline-none focus:border-slate-400"
          >
            {rulesList.map((r) => {
              const count = r.id === "all" ? findings?.length || 0 : ruleCounts[r.id] || 0;
              return (
                <option key={r.id} value={r.id}>
                  {r.label} ({count})
                </option>
              );
            })}
          </select>

          {/* Inline Bulk Action Bar (visible only when checkedIds.length > 0) */}
          {checkedIds.length > 0 && (
            <div className="flex items-center gap-1.5 pl-2 border-l border-[#E2E8F0]">
              <span className="text-[11px] font-mono tabular-nums font-medium text-slate-900">
                {checkedIds.length} selected
              </span>
              <button
                type="button"
                onClick={() => handleBulkAction("recovery")}
                disabled={isSubmittingDecision}
                className="px-2 py-1 rounded text-[11px] font-medium bg-[#047857] text-white hover:bg-[#065F46] transition-colors disabled:opacity-50"
              >
                Recover
              </button>
              <button
                type="button"
                onClick={() => handleBulkAction("reject")}
                disabled={isSubmittingDecision}
                className="px-2 py-1 rounded text-[11px] font-medium bg-[#B91C1C] text-white hover:bg-[#991B1B] transition-colors disabled:opacity-50"
              >
                Dispute
              </button>
              <button
                type="button"
                onClick={() => setCheckedIds([])}
                className="px-2 py-1 rounded text-[11px] font-medium text-slate-600 hover:text-slate-900 border border-[#E2E8F0] bg-white hover:bg-slate-50 transition-colors"
              >
                Clear
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search
              className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none"
              aria-hidden="true"
            />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search vendor, invoice #, ID…"
              aria-label="Search exceptions"
              className="w-full h-7 pl-8 pr-7 bg-[#F8FAFC] border border-[#E2E8F0] rounded text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-slate-400 focus:bg-white"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
              >
                <X className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            ) : (
              <kbd className="absolute right-2 top-1/2 -translate-y-1/2 px-1 py-0.5 text-[10px] font-mono text-slate-400 bg-white border border-[#E2E8F0] rounded pointer-events-none">
                /
              </kbd>
            )}
          </div>

          {onRunPayrunSweep && (
            <button
              type="button"
              onClick={onRunPayrunSweep}
              disabled={runningSweep || loadingAction}
              className="inline-flex items-center gap-1.5 h-7 px-2.5 text-xs font-medium rounded bg-slate-900 hover:bg-slate-800 text-white transition-colors disabled:opacity-50 whitespace-nowrap shrink-0"
              title="Run automated pay-run sweep across pending batches"
            >
              {runningSweep ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
              )}
              <span>{runningSweep ? "Sweeping…" : "Run Pay-Run Sweep"}</span>
            </button>
          )}

          <a
            href={api.getExportCsvUrl()}
            download="findings.csv"
            className="inline-flex items-center gap-1.5 h-7 px-2.5 text-xs font-medium rounded border border-[#E2E8F0] bg-white hover:bg-slate-50 text-slate-700 transition-colors whitespace-nowrap shrink-0"
            title="Export findings to CSV"
          >
            <Download className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
            <span className="hidden sm:inline">Export CSV</span>
          </a>
        </div>
      </div>

      {/* Empty State or Master-Detail Split Pane (55% / 45%) */}
      {filteredFindings.length === 0 ? (
        <div className="p-12 text-center rounded-md border border-[#E2E8F0] bg-white space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">No matching exceptions</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {findings?.length === 0
              ? "Load the demo dataset or upload an invoice to run automated audit checks."
              : "Adjust your status, rule, or search filters."}
          </p>
          {findings?.length === 0 ? (
            <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
              <button
                type="button"
                onClick={onSeedDemo}
                disabled={loadingAction}
                className="px-3.5 py-1.5 rounded bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs transition-colors disabled:opacity-50"
              >
                Load Demo Dataset
              </button>
              {onOpenDemoGuide && (
                <button
                  type="button"
                  onClick={onOpenDemoGuide}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded border border-[#E2E8F0] bg-white hover:bg-slate-50 text-slate-700 font-medium text-xs transition-colors"
                >
                  <PlayCircle className="w-3.5 h-3.5 text-slate-500" />
                  <span>Open Demo Guide</span>
                </button>
              )}
            </div>
          ) : (
            <button
              type="button"
              onClick={resetFilters}
              className="px-3.5 py-1.5 rounded border border-[#E2E8F0] bg-white hover:bg-slate-50 text-slate-900 font-medium text-xs transition-colors"
            >
              Reset Filters
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[55fr_45fr] gap-4 items-start">
          {/* Left 55%: High-Density Master Ledger Table */}
          <div className="min-w-0 bg-white border border-[#E2E8F0] rounded-md overflow-hidden">
            <div className="max-h-[calc(100vh-280px)] overflow-y-auto overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 z-10 bg-[#F8FAFC] border-b border-[#E2E8F0] text-slate-500">
                  <tr className="h-9">
                    <th className="pl-3 pr-1 w-8">
                      <input
                        type="checkbox"
                        checked={allFilteredChecked}
                        onChange={toggleAllFiltered}
                        aria-label="Select all visible findings"
                        className="rounded border-slate-300 text-slate-900 focus:ring-0"
                      />
                    </th>
                    <th className="px-2 font-medium w-24 whitespace-nowrap">Rule</th>
                    <th className="px-2 font-medium">Vendor / Invoice</th>
                    <th className="px-2 font-medium text-right w-28 whitespace-nowrap">
                      At Risk
                    </th>
                    <th className="pl-2 pr-3 font-medium text-right w-24 whitespace-nowrap">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {filteredFindings.map((finding) => {
                    const isSelected = selectedFindingId === finding.finding_id;
                    const isChecked = checkedIds.includes(finding.finding_id);
                    const refs = finding.entity_refs || {};
                    const invList = refs.invoice_numbers || [];
                    const sevDot =
                      SEVERITY_DOT[(finding.severity || "low").toLowerCase()] ||
                      SEVERITY_DOT.low;

                    return (
                      <tr
                        key={finding.finding_id}
                        tabIndex={0}
                        aria-selected={isSelected}
                        onClick={() => onSelectFinding(finding.finding_id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onSelectFinding(finding.finding_id);
                          }
                        }}
                        className={`h-10 cursor-pointer focus-visible:outline-none focus-visible:bg-slate-100 ${
                          isSelected
                            ? "bg-slate-100 border-l-2 border-l-slate-900"
                            : "hover:bg-slate-50 border-l-2 border-l-transparent"
                        }`}
                      >
                        <td
                          className="pl-3 pr-1 align-middle"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleOne(finding.finding_id)}
                            aria-label={`Select ${finding.finding_id}`}
                            className="rounded border-slate-300 text-slate-900 focus:ring-0"
                          />
                        </td>

                        <td className="px-2 align-middle whitespace-nowrap">
                          <div className="inline-flex items-center gap-1.5">
                            <span
                              className={`w-1.5 h-1.5 rounded-full shrink-0 ${sevDot}`}
                              title={`Severity: ${finding.severity || "low"}`}
                            />
                            <RuleBadge ruleId={finding.rule_id} />
                          </div>
                        </td>

                        <td className="px-2 align-middle min-w-0 max-w-[220px]">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span
                              className="font-medium text-slate-900 truncate"
                              title={finding.title}
                            >
                              {refs.vendor_id || "Vendor"}
                            </span>
                            <span className="text-slate-300 shrink-0">·</span>
                            <span
                              className="font-mono text-[11px] text-slate-500 truncate"
                              title={invList.join(", ")}
                            >
                              {invList[0] || finding.finding_id}
                            </span>
                          </div>
                        </td>

                        <td className="px-2 text-right whitespace-nowrap align-middle">
                          <span className="font-mono tabular-nums font-medium text-[#B91C1C]">
                            {formatCurrency(finding.amount_at_risk, finding.currency)}
                          </span>
                        </td>

                        <td className="pl-2 pr-3 text-right whitespace-nowrap align-middle">
                          <StatusBadge status={finding.status} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="px-3 py-2 border-t border-[#E2E8F0] bg-[#F8FAFC] text-[11px] text-slate-500 flex items-center justify-between tabular-nums">
              <span>
                Showing {filteredFindings.length} of {findings.length} flagged bills
              </span>
            </div>
          </div>

          {/* Right 45%: Sticky Evidence & Proof Trail Inspector */}
          <div className="min-w-0 lg:sticky lg:top-16">
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
