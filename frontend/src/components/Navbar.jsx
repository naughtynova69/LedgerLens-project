import React, { useState, useRef, useEffect } from "react";
import {
  Terminal,
  Upload,
  Database,
  FileText,
  PlayCircle,
  MoreHorizontal,
} from "lucide-react";
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
  onOpenDemoGuide,
  loadingAction,
  workspaces,
  activeWorkspaceId,
  onChangeWorkspace,
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const openCount = stats?.by_status?.open ?? 0;

  const navItems = [
    { id: "exceptions", label: "Exceptions", badge: openCount },
    { id: "activity", label: "Activity" },
    { id: "rules", label: "Rules & Graph" },
    { id: "cloud", label: "Integrations" },
  ];

  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuOpen]);

  return (
    <header className="sticky top-0 z-40 h-12 w-full border-b border-[var(--border-hairline)] bg-[var(--bg-surface)]/95 backdrop-blur">
      <div className="max-w-[1600px] h-full mx-auto px-4 flex items-center justify-between gap-3 flex-nowrap">
        {/* Left: Wordmark, Status Dot & Concise Primary Surface Tabs */}
        <div className="flex items-center gap-4 min-w-0 flex-nowrap">
          <button
            type="button"
            onClick={() => setActiveTab("exceptions")}
            className="flex items-center gap-2 shrink-0 text-left rounded-md py-1"
          >
            <span className="text-[14px] font-semibold tracking-[-0.01em] text-[var(--text-primary)]">
              LedgerLens
            </span>
            <span
              className="inline-flex items-center gap-1.5 text-[11px] font-medium text-[var(--text-muted)]"
              title={isOnline ? "Rules engine online" : "Backend unreachable"}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isOnline ? "bg-[var(--ok-dot)]" : "bg-[var(--risk-dot)]"
                }`}
              />
              <span className="hidden xl:inline">
                {isOnline ? "Live" : "Offline"}
              </span>
            </span>
          </button>

          <nav
            className="flex items-center gap-1 flex-nowrap"
            aria-label="Primary surfaces"
          >
            {navItems.map((item) => {
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  aria-current={active ? "page" : undefined}
                  className={`inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md text-xs font-medium whitespace-nowrap shrink-0 transition-colors duration-100 ${
                    active
                      ? "bg-[var(--bg-subtle)] text-[var(--text-primary)] border border-[var(--border-hairline)]"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-canvas)] border border-transparent"
                  }`}
                >
                  <span>{item.label}</span>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full text-[10px] font-mono tabular-nums bg-[var(--risk-bg)] text-[var(--risk-fg)] border border-[var(--risk-border)] leading-none">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Right: Max 4 Primary Controls + Compact Demo Overflow Menu */}
        <div className="flex items-center gap-1.5 shrink-0 flex-nowrap">
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
            className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-medium rounded-md border border-[var(--border-strong)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)] transition-colors duration-100 disabled:opacity-50 whitespace-nowrap shrink-0"
          >
            <Upload className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
            <span>Upload</span>
          </button>

          <button
            type="button"
            onClick={onOpenCopilot}
            className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-medium rounded-md border border-[var(--border-strong)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)] transition-colors duration-100 whitespace-nowrap shrink-0"
          >
            <Terminal className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
            <span>CFO Copilot</span>
          </button>

          <button
            type="button"
            onClick={onOpenMemoModal}
            className="inline-flex items-center gap-1.5 h-8 px-2.5 text-xs font-medium rounded-md bg-[var(--text-primary)] hover:bg-slate-800 text-white transition-colors duration-100 whitespace-nowrap shrink-0"
          >
            <FileText className="w-3.5 h-3.5 text-slate-300" />
            <span>CFO Memo</span>
          </button>

          {/* Compact Demo / Overflow Menu */}
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((prev) => !prev)}
              aria-label="Demo & tools menu"
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              title="Demo & tools"
              className="inline-flex items-center justify-center h-8 w-8 rounded-md border border-[var(--border-hairline)] bg-[var(--bg-surface)] hover:bg-[var(--bg-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors duration-100 shrink-0"
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>

            {menuOpen && (
              <div
                role="menu"
                aria-label="Demo & tools"
                className="absolute right-0 mt-1.5 w-44 rounded-lg border border-[var(--border-hairline)] bg-[var(--bg-surface)] shadow-sm py-1 z-50"
              >
                <button
                  type="button"
                  role="menuitem"
                  disabled={loadingAction}
                  onClick={() => {
                    setMenuOpen(false);
                    onSeedDemo && onSeedDemo();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] disabled:opacity-50 text-left"
                >
                  <Database className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
                  <span>Load Demo</span>
                </button>
                {onOpenDemoGuide && (
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      onOpenDemoGuide();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] text-left"
                  >
                    <PlayCircle className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
                    <span>Demo Guide</span>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
