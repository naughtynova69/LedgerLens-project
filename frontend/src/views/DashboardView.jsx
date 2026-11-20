import React from "react";
import {
  ShieldAlert,
  DollarSign,
  TrendingDown,
  AlertTriangle,
  ArrowRight,
  Database,
  Layers,
  ChevronRight,
  FileCheck2,
  CheckCircle2,
} from "lucide-react";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/SeverityBadge";
import { RuleBadge } from "../components/RuleBadge";
import { StatusBadge } from "../components/StatusBadge";
import { GraphStatsCard } from "../components/GraphStatsCard";
import { formatCurrency, formatConfidence } from "../utils/formatters";

export function DashboardView({
  stats,
  findings,
  onSelectFinding,
  onNavigateTab,
  onSeedDemo,
  loadingAction,
}) {
  const topFindings = (findings || []).slice(0, 6);

  const rulesMeta = [
    { id: "R1", name: "Duplicate & Near-Duplicate Invoices", desc: "Fuzzy invoice numbers, dates, vendor variants & PO double-billing" },
    { id: "R2", name: "Contract Price Leakage", desc: "Invoiced unit rates exceeding negotiated contract & discount terms" },
    { id: "R3", name: "PO Mismatch & Overbilling", desc: "Cumulative billed qty > PO limit, premature or unordered items" },
    { id: "R4", name: "Currency & Tax Errors", desc: "Currency mismatches, FX rate drift, invalid GST & duplicate tax lines" },
    { id: "R5", name: "Cancelled-Service Leakage", desc: "Charges billed after contract termination, cancellation, or expiry" },
    { id: "R6", name: "Split-Invoice / PO Split Billing", desc: "Same PO split across consecutive invoices to dodge duplicate checks" },
    { id: "R7", name: "GRN Mismatch", desc: "Invoices billed without a matching goods-receipt note" },
    { id: "R8", name: "Cross-Entity Duplicate & Splitting (Graph)", desc: "Distinct vendors sharing a bank/tax identifier billing near-identical or split invoices" },
    { id: "R9", name: "Approver-Vendor Collusion (Graph)", desc: "Approvers linked to their vendor via shared bank account, address, or phone" },
    { id: "R10", name: "Contract Lineage & Unapplied Credits (Graph)", desc: "Invoices billed at superseded amendment rates; OPEN credit notes left on the table" },
  ];

  const openExceptionsCount = stats?.by_status?.open ?? 0;

  return (
    <div className="space-y-6">
      {/* Pre-payment Neuro-Symbolic Hero Strip */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        <div className="space-y-1.5 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-[#ECFDF5] border border-[#A7F3D0] text-[#059669] text-[11px] font-bold uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-[#059669]" />
            Pre-Payment AP Audit Gate
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
            Explainable Money-Leak Audit Workstation
          </h1>
          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
            Gemini 3.8 Vision Flash extracts documents and writes CFO narratives; pure deterministic Python rules
            (R1–R5) compute every risk figure and line-level proof trail. The LLM is never the judge.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
          <button
            onClick={() => onNavigateTab("findings")}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs transition-colors"
          >
            <ShieldAlert className="w-4 h-4 text-emerald-400" />
            <span>Open Proof Trail Explorer ({stats?.total_findings || 0})</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <button
            onClick={() => onNavigateTab("memo")}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs border border-slate-300 transition-colors"
          >
            <FileCheck2 className="w-4 h-4 text-[#059669]" />
            <span>CFO Audit Memo</span>
          </button>
        </div>
      </div>

      {/* 4 Required KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Spend Audited"
          value={formatCurrency(stats?.total_audited_spend ?? 0)}
          subtext={`${stats?.batches_count || 0} ingested batch(es)`}
          icon={DollarSign}
          variant="default"
        />
        <StatCard
          title="Total Money at Risk"
          value={formatCurrency(stats?.total_at_risk ?? 0)}
          subtext={`Open risk: ${formatCurrency(stats?.open_at_risk ?? 0)}`}
          icon={AlertTriangle}
          variant="critical"
        />
        <StatCard
          title="Open Exceptions (R1–R5)"
          value={openExceptionsCount}
          subtext={`${stats?.by_severity?.critical || 0} Critical · ${stats?.by_severity?.high || 0} High`}
          icon={ShieldAlert}
          variant="amber"
        />
        <StatCard
          title="Recovered / Blocked"
          value={formatCurrency(stats?.recovered_amount ?? 0)}
          subtext="Stopped pre-payment or in clawback"
          icon={TrendingDown}
          variant="emerald"
        />
      </div>

      {/* Embedded Knowledge Graph KPI */}
      <GraphStatsCard onToast={onToast} />

      {/* Two Column Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Rule Category Exposure */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#059669]" />
              <span>Deterministic Rule Coverage (R1–R10)</span>
            </h2>
            <button
              onClick={() => onNavigateTab("rules")}
              className="text-xs font-semibold text-[#059669] hover:text-[#047857]"
            >
              Inspect Logic →
            </button>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-2.5 shadow-sm">
            {rulesMeta.map((r) => {
              const count = stats?.by_rule?.[r.id] || 0;
              return (
                <div
                  key={r.id}
                  onClick={() => onNavigateTab("findings")}
                  className="group flex items-center justify-between p-3 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-200/80 cursor-pointer transition-colors"
                >
                  <div className="flex items-start gap-3 min-w-0 pr-3">
                    <RuleBadge ruleId={r.id} />
                    <div className="min-w-0">
                      <p className="text-xs sm:text-sm font-semibold text-slate-900 truncate">
                        {r.name}
                      </p>
                      <p className="text-xs text-slate-500 truncate">{r.desc}</p>
                    </div>
                  </div>
                  <span
                    className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-mono tabular-nums font-bold border ${
                      count > 0
                        ? "bg-[#FEF2F2] text-[#DC2626] border-[#FECACA]"
                        : "bg-white text-slate-500 border-slate-200"
                    }`}
                  >
                    {count} {count === 1 ? "alert" : "alerts"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Exception Feed */}
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-[#DC2626]" />
              <span>Flagged Spend Exceptions</span>
            </h2>
            <button
              onClick={() => onNavigateTab("findings")}
              className="text-xs font-semibold text-[#059669] hover:text-[#047857]"
            >
              Open Split-View ({findings?.length || 0}) →
            </button>
          </div>

          {topFindings.length === 0 ? (
            <div className="p-10 text-center rounded-xl border border-slate-200 bg-white space-y-3 shadow-sm">
              <div className="w-10 h-10 rounded-full bg-[#ECFDF5] text-[#059669] flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">No Audit Exceptions Loaded Yet</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Click below to load the official 5-file Buildathon dataset (6 planted anomalies + 4 clean controls).
              </p>
              <button
                onClick={onSeedDemo}
                disabled={loadingAction}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#059669] hover:bg-[#047857] text-white font-semibold text-xs transition-colors"
              >
                <Database className="w-4 h-4" />
                <span>Load Demo Dataset (6 Planted Anomalies)</span>
              </button>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 shadow-sm overflow-hidden">
              {topFindings.map((finding) => (
                <div
                  key={finding.finding_id}
                  onClick={() => {
                    onSelectFinding(finding.finding_id);
                    onNavigateTab("findings");
                  }}
                  className="p-4 hover:bg-slate-50 cursor-pointer transition-colors flex items-center justify-between gap-4 group"
                >
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-900">
                        {finding.finding_id}
                      </span>
                      <RuleBadge ruleId={finding.rule_id} />
                      <SeverityBadge severity={finding.severity} />
                      <StatusBadge status={finding.status} />
                    </div>
                    <p className="text-sm font-semibold text-slate-900 group-hover:text-[#059669] truncate">
                      {finding.title}
                    </p>
                    <p className="text-xs text-slate-500 truncate">{finding.summary}</p>
                  </div>

                  <div className="text-right shrink-0 space-y-1">
                    <div className="text-base font-bold font-mono tabular-nums text-[#DC2626]">
                      {formatCurrency(finding.amount_at_risk, finding.currency)}
                    </div>
                    <div className="text-[11px] font-mono tabular-nums text-slate-500 inline-flex items-center gap-1">
                      <span>{formatConfidence(finding.confidence)}</span>
                      <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-700" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
