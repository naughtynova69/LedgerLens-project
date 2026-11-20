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
        className="w-3.5 h-3.5 text-gray-500 absolute left-2.5 pointer-events-none"
        aria-hidden="true"
      />
      <select
        aria-label="Client workspace"
        value={activeWorkspaceId || ""}
        disabled={!hasWorkspaces}
        onChange={(e) => onChangeWorkspace && onChangeWorkspace(e.target.value)}
        className="appearance-none pl-7 pr-7 py-1.5 text-xs font-medium rounded-lg border border-gray-200 bg-white hover:bg-gray-50 text-[#111827] focus:outline-none focus:ring-2 focus:ring-slate-900/15 focus:border-slate-400 transition-colors disabled:opacity-60 cursor-pointer"
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
        className="w-3.5 h-3.5 text-gray-400 absolute right-2 pointer-events-none"
        aria-hidden="true"
      />
    </div>
  );
}
