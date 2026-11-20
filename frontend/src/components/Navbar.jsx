import React from "react";
import {
  ShieldAlert,
  Play,
  Database,
  FileText,
  Activity,
  UploadCloud,
  FileCheck2,
  Terminal,
  BookOpen,
} from "lucide-react";
import { formatCurrency } from "../utils/formatters";

export function Navbar({
  activeTab,
  setActiveTab,
  stats,
  isOnline,
  onSeedDemo,
  onRunDetect,
  loadingAction,
}) {
  const navItems = [
    { id: "dashboard", label: "Overview", icon: Activity },
    {
      id: "findings",
      label: "Exception Queue",
      icon: ShieldAlert,
      badge: stats?.open_findings ?? stats?.by_status?.open,
    },
    { id: "upload", label: "Ingest & Upload", icon: UploadCloud },
    { id: "memo", label: "Audit Memo", icon: FileCheck2 },
    { id: "rules", label: "Detection Engine", icon: BookOpen },
    { id: "audit", label: "Audit Trail", icon: Terminal },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/90 bg-[#090D16]/90 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab("dashboard")}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 via-teal-500 to-cyan-400 p-[1px] shadow-lg shadow-emerald-950/30">
              <div className="w-full h-full bg-[#0D1525] rounded-[11px] flex items-center justify-center">
                <ShieldAlert className="w-5 h-5 text-emerald-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold tracking-tight text-white font-mono">
                  Ledger<span className="text-emerald-400">Lens</span>
                </span>
                <span className="text-[10px] font-semibold tracking-wider uppercase px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  v0.1 AI Auditor
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                Explainable Autonomous Spend Protection
              </p>
            </div>
          </div>

          {/* Quick Metrics & Actions */}
          <div className="flex items-center gap-3 sm:gap-4">
            {/* Total at Risk Badge */}
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs">
              <span className="text-rose-300 font-medium">Total at Risk:</span>
              <span className="font-mono font-bold text-rose-400">
                {formatCurrency(stats?.open_at_risk ?? stats?.total_at_risk ?? 0)}
              </span>
            </div>

            {/* Backend Health Status */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                isOnline
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "bg-rose-500/10 text-rose-400 border-rose-500/20"
              }`}
              title={isOnline ? "Backend API connected" : "Backend unreachable"}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isOnline ? "bg-emerald-400 animate-pulse" : "bg-rose-500"
                }`}
              />
              <span className="hidden sm:inline">{isOnline ? "Engine Live" : "Offline"}</span>
            </div>

            {/* Quick Demo Seed */}
            <button
              onClick={onSeedDemo}
              disabled={loadingAction}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 transition-all shadow-md shadow-emerald-950/20 disabled:opacity-50"
              title="Populate 6 planted anomalies + clean controls"
            >
              <Database className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Load Demo Data</span>
              <span className="sm:hidden">Demo</span>
            </button>

            {/* Run Detect */}
            <button
              onClick={onRunDetect}
              disabled={loadingAction}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden sm:inline">Run Detect</span>
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-1 sm:space-x-2 border-t border-slate-800/60 overflow-x-auto py-2 no-scrollbar">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all duration-200 ${
                  active
                    ? "bg-slate-800 text-emerald-400 border border-slate-700 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${active ? "text-emerald-400" : "text-slate-400"}`} />
                <span>{item.label}</span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
