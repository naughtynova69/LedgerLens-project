import React from "react";
import {
  ShieldAlert,
  DollarSign,
  TrendingDown,
  CheckCircle,
  FileText,
  AlertTriangle,
  ArrowRight,
  Database,
  Flame,
  Layers,
  ChevronRight,
} from "lucide-react";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/SeverityBadge";
import { RuleBadge } from "../components/RuleBadge";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatConfidence } from "../utils/formatters";

export function DashboardView({
  stats,
  findings,
  onSelectFinding,
  onNavigateTab,
  onSeedDemo,
  loadingAction,
}) {
  const topFindings = (findings || []).slice(0, 5);

  const rulesMeta = [
    { id: "R1", name: "Duplicate Invoices", desc: "Same invoice resubmitted with altered numbers" },
    { id: "R2", name: "Contract Price Leakage", desc: "Invoiced rates exceeding contracted agreement" },
    { id: "R3", name: "PO Overbilling", desc: "Billed quantity above authorized PO limit" },
    { id: "R4", name: "Currency & Tax Errors", desc: "Wrong currency, invalid GST on exempt services" },
    { id: "R5", name: "Cancelled Service", desc: "Recurring charges billed after contract cancellation" },
  ];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Hero / Executive Banner */}
      <div className="relative rounded-3xl overflow-hidden border border-slate-800/80 bg-gradient-to-r from-[#0C1222] via-[#0E1A2E] to-[#0A1728] p-6 sm:p-8 shadow-2xl">
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Continuous Spend Audit Active
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-white tracking-tight">
              Explainable AI Auditor for Enterprise Spend
            </h1>
            <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
              Every flagged dollar links to mathematical evidence: contracts, purchase orders,
              invoice lines, and payments. The rules engine decides; Gemini explains for CFOs.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => onNavigateTab("findings")}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-sm transition-all shadow-lg shadow-emerald-950/30"
            >
              <ShieldAlert className="w-4 h-4" />
              <span>Review Exception Queue ({stats?.total_findings || 0})</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => onNavigateTab("memo")}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-medium text-sm border border-slate-700 transition-all"
            >
              <FileText className="w-4 h-4 text-cyan-400" />
              <span>View Audit Memo</span>
            </button>
          </div>
        </div>

        {/* Subtle background glow */}
        <div className="absolute -right-20 -bottom-20 w-80 h-80 rounded-full bg-emerald-500/5 blur-3xl pointer-events-none" />
      </div>

      {/* KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        <StatCard
          title="Total Spend at Risk"
          value={formatCurrency(stats?.open_at_risk ?? stats?.total_at_risk ?? 0)}
          subtext="Detected across active invoices"
          icon={AlertTriangle}
          variant="critical"
          highlight
        />
        <StatCard
          title="Total Audited Spend"
          value={formatCurrency(stats?.total_audited_spend || 104527.2)}
          subtext="Across sample & uploaded ledger"
          icon={DollarSign}
          variant="default"
        />
        <StatCard
          title="Recovered / Blocked"
          value={formatCurrency(stats?.recovered_amount || 0)}
          subtext="Protected from disbursement"
          icon={TrendingDown}
          variant="emerald"
        />
        <StatCard
          title="Exceptions Flagged"
          value={stats?.total_findings || 0}
          subtext={`${stats?.by_severity?.critical || 0} Critical · ${stats?.by_severity?.high || 0} High`}
          icon={Flame}
          variant="blue"
        />
      </div>

      {/* Two Column Layout: Rules Exposure Breakdown & Quick Exceptions Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Rules Breakdown */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" />
              <span>Exposure by Rule Category</span>
            </h2>
            <button
              onClick={() => onNavigateTab("rules")}
              className="text-xs text-emerald-400 hover:text-emerald-300 font-medium"
            >
              Explore Math →
            </button>
          </div>

          <div className="bg-[#0D1424] border border-slate-800/80 rounded-2xl p-5 space-y-3">
            {rulesMeta.map((r) => {
              const count = stats?.by_rule?.[r.id] || 0;
              return (
                <div
                  key={r.id}
                  onClick={() => onNavigateTab("findings")}
                  className="group flex items-center justify-between p-3 rounded-xl bg-slate-900/60 hover:bg-slate-800/80 border border-slate-800/50 hover:border-slate-700 cursor-pointer transition-all"
                >
                  <div className="flex items-center gap-3">
                    <RuleBadge ruleId={r.id} />
                    <div>
                      <p className="text-sm font-semibold text-white group-hover:text-emerald-300 transition-colors">
                        {r.name}
                      </p>
                      <p className="text-xs text-slate-400">{r.desc}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-mono font-bold ${
                        count > 0
                          ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      {count} {count === 1 ? "alert" : "alerts"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* ROI Metric Callout */}
          <div className="p-5 rounded-2xl border border-emerald-900/30 bg-emerald-950/20 backdrop-blur-sm">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold uppercase tracking-wider">
              <CheckCircle className="w-4 h-4" />
              Audit Defensibility Guarantee
            </div>
            <p className="text-xs text-slate-300 mt-2 leading-relaxed">
              Every finding is backed by <code className="text-emerald-300 font-mono">EvidenceRef</code> chips
              (exact source document, record ID, and comparison field). Zero black-box hallucinations.
            </p>
          </div>
        </div>

        {/* Top High-Risk Findings Feed */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              <span>Top Exposure Items</span>
            </h2>
            <button
              onClick={() => onNavigateTab("findings")}
              className="text-xs text-emerald-400 hover:text-emerald-300 font-medium"
            >
              View All ({findings?.length || 0}) →
            </button>
          </div>

          {topFindings.length === 0 ? (
            <div className="p-12 text-center rounded-2xl border border-slate-800 bg-[#0D1424] space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-white">No Exceptions Flagged</h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                Your payment ledger and invoice queue are clear, or no documents have been analyzed yet.
              </p>
              <button
                onClick={onSeedDemo}
                disabled={loadingAction}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-semibold text-xs transition-all"
              >
                <Database className="w-4 h-4" />
                <span>Load Demo Dataset (6 Planted Anomalies)</span>
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {topFindings.map((finding) => (
                <div
                  key={finding.finding_id}
                  onClick={() => onSelectFinding(finding.finding_id)}
                  className="group p-4 rounded-2xl bg-[#0D1424] hover:bg-[#111A2E] border border-slate-800/80 hover:border-slate-700/90 cursor-pointer transition-all duration-200 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <SeverityBadge severity={finding.severity} />
                        <RuleBadge ruleId={finding.rule_id} />
                        <span className="text-xs font-mono text-slate-400">
                          {finding.finding_id}
                        </span>
                      </div>
                      <h4 className="text-sm font-semibold text-white group-hover:text-emerald-300 transition-colors truncate">
                        {finding.title}
                      </h4>
                      <p className="text-xs text-slate-400 line-clamp-2">
                        {finding.summary}
                      </p>
                    </div>

                    <div className="text-right flex flex-col items-end shrink-0">
                      <span className="text-base sm:text-lg font-bold font-mono text-rose-400">
                        {formatCurrency(finding.amount_at_risk, finding.currency)}
                      </span>
                      <div className="mt-1">
                        <StatusBadge status={finding.status} />
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="font-mono">
                      Confidence: {formatConfidence(finding.confidence)}
                    </span>
                    <span className="inline-flex items-center text-emerald-400 group-hover:translate-x-0.5 transition-transform font-medium">
                      Inspect Proof Trail <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                    </span>
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
