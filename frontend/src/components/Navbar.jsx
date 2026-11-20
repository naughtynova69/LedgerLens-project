import React from "react";
import { Sparkles, Upload, Database, Download, FileText } from "lucide-react";
import { api } from "../api";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";

export function Navbar({
  activeTab,
  setActiveTab,
  stats,
  isOnline,
  onSeedDemo,
  onOpenUploadModal,
  onOpenMemoModal,
  onOpenCopilot,
  loadingAction,
  workspaces,
  activeWorkspaceId,
  onChangeWorkspace,
}) {
  const openCount = stats?.by_status?.open ?? 0;

  const navItems = [
    { id: "exceptions", label: "Exceptions", badge: openCount },
    { id: "activity", label: "Activity" },
    { id: "cloud", label: "Cloud & Policy" },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-gray-200 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-4">
        {/* Left: Wordmark, Status Dot & 3 Surface Tabs */}
        <div className="flex items-center gap-6 min-w-0">
          <button
            type="button"
            onClick={() => setActiveTab("exceptions")}
            className="flex items-center gap-2.5 shrink-0 text-left"
          >
            <span className="text-sm font-semibold tracking-tight text-[#111827]">
              LedgerLens
            </span>
            <span
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-gray-500"
              title={isOnline ? "Rules engine online" : "Backend unreachable"}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isOnline ? "bg-[#047857]" : "bg-[#B91C1C]"
                }`}
              />
              <span className="hidden sm:inline">{isOnline ? "Live" : "Offline"}</span>
            </span>
          </button>

          <nav className="flex items-center gap-1 overflow-x-auto" aria-label="Primary surfaces">
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
                      ? "bg-gray-100 text-[#111827] shadow-2xs"
                      : "text-gray-500 hover:text-[#111827] hover:bg-gray-50"
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

        {/* Right: Quiet Action Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {workspaces && workspaces.length > 0 && (
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
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors disabled:opacity-50"
          >
            <Upload className="w-3.5 h-3.5 text-gray-500" />
            <span>Upload</span>
          </button>

          <button
            type="button"
            onClick={onSeedDemo}
            disabled={loadingAction}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors disabled:opacity-50"
          >
            <Database className="w-3.5 h-3.5 text-gray-500" />
            <span>Load Demo</span>
          </button>

          <a
            href={api.getExportCsvUrl()}
            download="findings.csv"
            className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-gray-500" />
            <span>Export CSV</span>
          </a>

          <button
            type="button"
            onClick={onOpenCopilot}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-[#111827] transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>CFO Copilot</span>
          </button>

          <button
            type="button"
            onClick={onOpenMemoModal}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg bg-[#111827] hover:bg-gray-800 text-white transition-colors"
          >
            <FileText className="w-3.5 h-3.5 text-gray-200" />
            <span>CFO Memo</span>
          </button>
        </div>
      </div>
    </header>
  );
}
