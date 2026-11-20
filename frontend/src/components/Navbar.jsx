import React from "react";
import {
  ShieldCheck,
  Database,
  Upload,
  Activity,
  ShieldAlert,
  FileCheck2,
  BookOpen,
  Terminal,
  UploadCloud,
} from "lucide-react";

export function Navbar({
  activeTab,
  setActiveTab,
  stats,
  isOnline,
  onSeedDemo,
  onOpenUploadModal,
  loadingAction,
}) {
  const openCount = stats?.by_status?.open ?? 0;

  const navItems = [
    { id: "dashboard", label: "Overview", icon: Activity },
    {
      id: "findings",
      label: "Exception Queue",
      icon: ShieldAlert,
      badge: openCount,
    },
    { id: "memo", label: "CFO Audit Memo", icon: FileCheck2 },
    { id: "audit", label: "Audit Log", icon: Terminal },
    { id: "upload", label: "Batches & Feeds", icon: UploadCloud },
    { id: "rules", label: "Rules R1–R5", icon: BookOpen },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200 bg-white/95 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3 py-3">
          {/* Brand Header */}
          <div
            className="flex items-center gap-3 cursor-pointer"
            onClick={() => setActiveTab("dashboard")}
          >
            <div className="w-10 h-10 rounded-xl bg-slate-900 flex items-center justify-center shadow-sm shrink-0">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base sm:text-lg font-bold tracking-tight text-slate-900">
                  LedgerLens
                </span>
                <span className="hidden md:inline-block text-xs font-medium text-slate-500">
                  — Explainable AI Money-Leak Auditor
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                Pre-Payment Neuro-Symbolic AP Gate · Deterministic Rules R1–R5
              </p>
            </div>
          </div>

          {/* Right Command Controls */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${
                isOnline
                  ? "bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]"
                  : "bg-[#FEF2F2] text-[#DC2626] border-[#FECACA]"
              }`}
              title={isOnline ? "FastAPI rules engine online" : "Backend unreachable"}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isOnline ? "bg-[#059669]" : "bg-[#DC2626]"
                }`}
              />
              <span>{isOnline ? "Engine Live" : "Offline"}</span>
            </div>

            <button
              onClick={onOpenUploadModal}
              disabled={loadingAction}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 transition-colors disabled:opacity-50"
            >
              <Upload className="w-3.5 h-3.5 text-slate-600" />
              <span>Upload CSV/PDF</span>
            </button>

            <button
              onClick={onSeedDemo}
              disabled={loadingAction}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-[#059669] hover:bg-[#047857] text-white transition-colors shadow-sm disabled:opacity-50"
            >
              <Database className="w-3.5 h-3.5" />
              <span>Load Demo Dataset (6 Planted Anomalies)</span>
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-1 border-t border-slate-100 overflow-x-auto py-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
                  active
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold tabular-nums ${
                      active
                        ? "bg-rose-500 text-white"
                        : "bg-[#FEF2F2] text-[#DC2626] border border-[#FECACA]"
                    }`}
                  >
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
