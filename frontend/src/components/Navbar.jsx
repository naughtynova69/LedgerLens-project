import React, { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Cloud,
  Database,
  FileText,
  PlayCircle,
  Sparkles,
  Upload,
  UserCheck,
  Wrench,
} from "lucide-react";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";
import { useAccountMemory } from "../context/AccountMemoryContext";

export function Navbar({
  activeTab,
  setActiveTab,
  stats,
  isOnline,
  gcpStatus,
  onSeedDemo,
  onOpenUploadModal,
  onOpenMemoModal,
  onOpenCopilot,
  onOpenDemoGuide,
  loadingAction,
  workspaces,
  activeWorkspaceId,
  onChangeWorkspace,
}) {
  const { profile, updateProfile, activityLog, syncStatus } = useAccountMemory();
  const [toolsOpen, setToolsOpen] = useState(false);
  const toolsRef = useRef(null);

  const openCount = stats?.by_status?.open ?? 0;
  const gcpConnectedCount = Object.values(gcpStatus?.services || {}).filter(
    (s) => s?.mode === "configured"
  ).length;

  useEffect(() => {
    if (!toolsOpen) return undefined;
    const handleOutside = (e) => {
      if (toolsRef.current && !toolsRef.current.contains(e.target)) {
        setToolsOpen(false);
      }
    };
    const handleEscape = (e) => {
      if (e.key === "Escape") setToolsOpen(false);
    };
    document.addEventListener("mousedown", handleOutside);
    window.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [toolsOpen]);

  const navItems = [
    { id: "exceptions", label: "Flagged Bills", badge: openCount },
    { id: "activity", label: "Activity" },
    { id: "rules", label: "Audit Rules" },
    { id: "cloud", label: "Google Cloud" },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[#E2E8F0] bg-white/95 backdrop-blur">
      <div className="max-w-[1600px] mx-auto px-4">
        <div className="min-h-13 py-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          {/* Left: Wordmark, Live Status & Primary Ledger Tabs */}
          <div className="flex flex-wrap items-center gap-4 sm:gap-6">
            <div className="flex items-center gap-2.5 shrink-0">
              <button
                type="button"
                onClick={() => setActiveTab("exceptions")}
                className="flex items-center gap-2.5 text-left rounded-md px-1 py-0.5 hover:bg-slate-50 transition-colors"
              >
                <span className="text-sm font-semibold tracking-tight text-slate-900">
                  LedgerLens
                </span>
                <span
                  className="inline-flex items-center gap-1.5 text-[11px] font-medium text-slate-500"
                  title={
                    isOnline
                      ? gcpStatus?.project_id
                        ? `Connected to ${gcpStatus.project_id} (${gcpStatus.location})`
                        : "Service online"
                      : "Service offline"
                  }
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      isOnline ? "bg-[#047857]" : "bg-[#B91C1C]"
                    }`}
                    aria-hidden="true"
                  />
                  <span className="hidden sm:inline">
                    {isOnline ? "Live" : "Offline"}
                  </span>
                </span>
              </button>

              {gcpStatus && (
                <button
                  type="button"
                  onClick={() => setActiveTab("cloud")}
                  className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-50 border border-[#E2E8F0] text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors tabular-nums"
                  title="View Google Cloud integration status"
                >
                  <Cloud className="w-3 h-3 text-slate-500" aria-hidden="true" />
                  <span>
                    {gcpConnectedCount > 0
                      ? `GCP · ${gcpConnectedCount}/6`
                      : gcpStatus.location || "Cloud Ready"}
                  </span>
                </button>
              )}
            </div>

            <nav
              className="flex flex-wrap items-center gap-1"
              aria-label="Primary navigation"
            >
              {navItems.map((item) => {
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveTab(item.id)}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
                      active
                        ? "bg-slate-100 text-slate-900 border border-[#E2E8F0]"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent"
                    }`}
                  >
                    <span>{item.label}</span>
                    {item.badge !== undefined && item.badge > 0 && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono tabular-nums bg-[#FEF2F2] text-[#991B1B] border border-[#FECACA] leading-none">
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Right: Workspace, Primary Actions & Secondary Sandbox / Tools */}
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            {workspaces && workspaces.length > 1 && (
              <WorkspaceSwitcher
                workspaces={workspaces}
                activeWorkspaceId={activeWorkspaceId}
                onChangeWorkspace={onChangeWorkspace}
              />
            )}

            <button
              type="button"
              onClick={onOpenUploadModal}
              disabled={loadingAction}
              className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-medium rounded-md border border-[#E2E8F0] bg-white hover:bg-slate-50 text-slate-700 transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              <Upload className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
              <span>Upload</span>
            </button>

            <button
              type="button"
              onClick={onOpenCopilot}
              className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-medium rounded-md border border-[#E2E8F0] bg-white hover:bg-slate-50 text-slate-900 transition-colors whitespace-nowrap"
            >
              <Sparkles className="w-3.5 h-3.5 text-slate-700" aria-hidden="true" />
              <span>CFO Copilot</span>
            </button>

            <button
              type="button"
              onClick={onOpenMemoModal}
              className="inline-flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md bg-slate-900 hover:bg-slate-800 text-white transition-colors whitespace-nowrap"
            >
              <FileText className="w-3.5 h-3.5 text-slate-300" aria-hidden="true" />
              <span>Report</span>
            </button>

            {/* Secondary Sandbox / Tools Menu */}
            <div className="relative" ref={toolsRef}>
              <button
                type="button"
                onClick={() => setToolsOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={toolsOpen}
                className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-medium rounded-md border border-[#E2E8F0] bg-[#F8FAFC] hover:bg-slate-100 text-slate-700 transition-colors whitespace-nowrap"
              >
                <Wrench className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
                <span className="hidden sm:inline">Sandbox / Tools</span>
                <ChevronDown className="w-3 h-3 text-slate-400" aria-hidden="true" />
              </button>

              {toolsOpen && (
                <div
                  role="menu"
                  aria-label="Sandbox and account tools"
                  className="absolute right-0 mt-1.5 w-72 rounded-md border border-[#E2E8F0] bg-white shadow-lg z-50 divide-y divide-[#E2E8F0]"
                >
                  {/* Active Account Profile */}
                  <div className="p-3 space-y-2">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1">
                        <UserCheck className="w-3 h-3" aria-hidden="true" />
                        Reviewer Profile
                      </span>
                      <span className="font-mono text-[10px] text-slate-400">
                        {syncStatus === "synced" ? "Synced" : "Local"}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <input
                        type="text"
                        value={profile.name}
                        onChange={(e) => updateProfile({ name: e.target.value })}
                        aria-label="Reviewer name"
                        placeholder="Reviewer name…"
                        className="h-7 px-2 text-xs rounded border border-[#E2E8F0] bg-[#F8FAFC] text-slate-900 focus:bg-white focus:outline-none focus:border-slate-400"
                      />
                      <input
                        type="text"
                        value={profile.role}
                        onChange={(e) => updateProfile({ role: e.target.value })}
                        aria-label="Reviewer role"
                        placeholder="Role…"
                        className="h-7 px-2 text-xs rounded border border-[#E2E8F0] bg-[#F8FAFC] text-slate-900 focus:bg-white focus:outline-none focus:border-slate-400"
                      />
                    </div>
                  </div>

                  {/* Sandbox Actions */}
                  <div className="p-1.5 space-y-0.5">
                    <button
                      type="button"
                      role="menuitem"
                      disabled={loadingAction}
                      onClick={() => {
                        setToolsOpen(false);
                        onSeedDemo?.();
                      }}
                      className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 transition-colors disabled:opacity-50 text-left"
                    >
                      <Database className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
                      <span>Seed Demo Dataset</span>
                    </button>

                    {onOpenDemoGuide && (
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setToolsOpen(false);
                          onOpenDemoGuide();
                        }}
                        className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded text-xs font-medium text-slate-700 hover:bg-slate-100 hover:text-slate-900 transition-colors text-left"
                      >
                        <PlayCircle className="w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
                        <span>Demo Guide</span>
                      </button>
                    )}
                  </div>

                  {/* Recent Cross-Page Activity */}
                  {activityLog.length > 0 && (
                    <div className="p-3 space-y-1.5 bg-[#F8FAFC]">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Recent Session Activity
                      </div>
                      <ul className="space-y-1 max-h-28 overflow-y-auto">
                        {activityLog.slice(0, 4).map((entry) => (
                          <li
                            key={entry.id}
                            className="text-[11px] text-slate-600 flex items-center justify-between gap-2"
                          >
                            <span className="truncate">
                              <span className="font-medium text-slate-800">{entry.action}</span>
                              {entry.detail ? ` · ${entry.detail}` : ""}
                            </span>
                            <span className="font-mono text-[10px] text-slate-400 shrink-0">
                              {entry.page}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
