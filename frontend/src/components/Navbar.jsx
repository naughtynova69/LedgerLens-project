import React from "react";
import { Sparkles, Upload, Database, FileText, PlayCircle, Cloud } from "lucide-react";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";

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
  const openCount = stats?.by_status?.open ?? 0;
  const gcpConnectedCount = Object.values(gcpStatus?.services || {}).filter(
    (s) => s?.mode === "configured"
  ).length;

  const navItems = [
    { id: "exceptions", label: "Flagged Bills", badge: openCount },
    { id: "activity", label: "Activity" },
    { id: "rules", label: "Audit Rules" },
    { id: "cloud", label: "Google Cloud" },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-gray-200 bg-white/95 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="min-h-14 py-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          {/* Left: Wordmark, Live Status & Minimal Tabs */}
          <div className="flex flex-wrap items-center gap-4 sm:gap-6">
            <div className="flex items-center gap-2.5 shrink-0">
              <button
                type="button"
                onClick={() => setActiveTab("exceptions")}
                className="flex items-center gap-2.5 text-left"
              >
                <span className="text-sm font-semibold tracking-tight text-[#111827]">
                  LedgerLens
                </span>
                <span
                  className="inline-flex items-center gap-1.5 text-[11px] font-medium text-gray-500"
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
                  className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-50 border border-gray-200 text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
                  title="View Google Cloud integration status"
                >
                  <Cloud className="w-3 h-3 text-indigo-600" />
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
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                      active
                        ? "bg-gray-100 text-[#111827] border border-gray-200/80"
                        : "text-gray-500 hover:text-[#111827] hover:bg-gray-50 border border-transparent"
                    }`}
                  >
                    <span>{item.label}</span>
                    {item.badge !== undefined && item.badge > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono tabular-nums bg-red-50/80 text-red-700 border border-red-200 leading-none">
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Right: Clean Action Controls */}
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            {workspaces && workspaces.length > 1 && (
              <WorkspaceSwitcher
                workspaces={workspaces}
                activeWorkspaceId={activeWorkspaceId}
                onChangeWorkspace={onChangeWorkspace}
              />
            )}

            {onOpenDemoGuide && (
              <button
                type="button"
                onClick={onOpenDemoGuide}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-indigo-200 bg-indigo-50/70 hover:bg-indigo-100/80 text-indigo-700 transition-colors whitespace-nowrap"
              >
                <PlayCircle className="w-3.5 h-3.5 text-indigo-600" />
                <span>Guide</span>
              </button>
            )}

            <button
              type="button"
              onClick={onOpenUploadModal}
              disabled={loadingAction}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              <Upload className="w-3.5 h-3.5 text-gray-500" />
              <span>Upload</span>
            </button>

            <button
              type="button"
              onClick={onSeedDemo}
              disabled={loadingAction}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              <Database className="w-3.5 h-3.5 text-gray-500" />
              <span>Load Demo</span>
            </button>

            <button
              type="button"
              onClick={onOpenCopilot}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-[#111827] transition-colors whitespace-nowrap"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>CFO Copilot</span>
            </button>

            <button
              type="button"
              onClick={onOpenMemoModal}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg bg-[#111827] hover:bg-gray-800 text-white transition-colors whitespace-nowrap"
            >
              <FileText className="w-3.5 h-3.5 text-gray-200" />
              <span>Report</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
