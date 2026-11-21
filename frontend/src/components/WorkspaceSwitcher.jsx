import React from "react";
import { Building2, ChevronDown } from "lucide-react";

export function WorkspaceSwitcher({
  workspaces = [],
  activeWorkspaceId,
  onChangeWorkspace,
}) {
  const hasWorkspaces = Array.isArray(workspaces) && workspaces.length > 0;

  return (
    <div className="relative inline-flex items-center">
      <Building2
        className="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-2.5 pointer-events-none"
        aria-hidden="true"
      />
      <select
        aria-label="Client workspace"
        value={activeWorkspaceId || ""}
        disabled={!hasWorkspaces}
        onChange={(e) => onChangeWorkspace && onChangeWorkspace(e.target.value)}
        className="h-8 appearance-none pl-7 pr-7 text-xs font-medium rounded-md border border-[var(--border-strong)] bg-[var(--bg-surface)] hover:bg-[var(--bg-canvas)] text-[var(--text-primary)] transition-colors duration-100 disabled:opacity-60 cursor-pointer max-w-[160px] truncate"
      >
        {!hasWorkspaces ? (
          <option value="">Default Workspace</option>
        ) : (
          workspaces.map((ws) => {
            const id = ws.id ?? ws.workspace_id;
            const label = ws.name || ws.client_name || id;
            return (
              <option key={id} value={id}>
                {label}
              </option>
            );
          })
        )}
      </select>
      <ChevronDown
        className="w-3.5 h-3.5 text-[var(--text-muted)] absolute right-2 pointer-events-none"
        aria-hidden="true"
      />
    </div>
  );
}
