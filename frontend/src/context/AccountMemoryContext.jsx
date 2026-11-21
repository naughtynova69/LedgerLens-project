import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api } from "../api";

const STORAGE_KEY = "ledgerlens_account_memory_v1";
const MAX_ACTIVITY_LOG = 25;
const MAX_COPILOT_HISTORY = 30;

export const DEFAULT_PROFILE = {
  account_id: "ap-controller",
  name: "AP Controller",
  role: "Finance Lead",
};

export const DEFAULT_FILTERS = {
  searchQuery: "",
  ruleFilter: "all",
  statusFilter: "all",
};

const INITIAL_MEMORY = {
  version: 1,
  profile: DEFAULT_PROFILE,
  activeWorkspaceId: "default",
  activeTab: "exceptions",
  filters: DEFAULT_FILTERS,
  selectedFindingId: null,
  activityLog: [],
  copilotByWorkspace: {},
};

function readStoredMemory() {
  try {
    if (typeof window === "undefined" || !window.localStorage) {
      return INITIAL_MEMORY;
    }
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return INITIAL_MEMORY;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return INITIAL_MEMORY;
    return {
      ...INITIAL_MEMORY,
      ...parsed,
      profile: {
        ...DEFAULT_PROFILE,
        ...(parsed.profile || {}),
      },
      filters: {
        ...DEFAULT_FILTERS,
        ...(parsed.filters || {}),
      },
      activityLog: Array.isArray(parsed.activityLog)
        ? parsed.activityLog.slice(0, MAX_ACTIVITY_LOG)
        : [],
      copilotByWorkspace:
        parsed.copilotByWorkspace && typeof parsed.copilotByWorkspace === "object"
          ? parsed.copilotByWorkspace
          : {},
    };
  } catch {
    return INITIAL_MEMORY;
  }
}

function writeStoredMemory(memory) {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(memory));
    }
  } catch {
    // Ignore storage quota or private-mode errors
  }
}

export function formatReviewerLabel(profile) {
  const name = (profile?.name || DEFAULT_PROFILE.name).trim();
  const role = (profile?.role || "").trim();
  return role ? `${name} (${role})` : name;
}

const AccountMemoryContext = createContext(null);

export function AccountMemoryProvider({ children }) {
  const [memory, setMemory] = useState(() => readStoredMemory());
  const [syncStatus, setSyncStatus] = useState("local-only");
  const hasHydratedRemoteRef = useRef(false);
  const syncTimerRef = useRef(null);

  // Hydrate from backend on mount (gracefully falls back to localStorage)
  useEffect(() => {
    let cancelled = false;
    const accountId = memory.profile?.account_id || DEFAULT_PROFILE.account_id;
    const workspaceId = memory.activeWorkspaceId || "default";

    if (typeof api.getAccountMemory !== "function") {
      return undefined;
    }

    api
      .getAccountMemory(accountId, workspaceId)
      .then((remote) => {
        if (cancelled || !remote || typeof remote !== "object") return;
        const remoteState = remote.memory || remote.data || remote;
        setMemory((prev) => {
          const merged = {
            ...prev,
            profile: {
              ...prev.profile,
              ...(remoteState.profile || {}),
              ...(remoteState.user_name ? { name: remoteState.user_name } : {}),
              ...(remoteState.user_role ? { role: remoteState.user_role } : {}),
            },
            activeWorkspaceId:
              remoteState.activeWorkspaceId ||
              remoteState.workspace_id ||
              prev.activeWorkspaceId,
            activeTab:
              remoteState.activeTab ||
              remoteState.active_tab ||
              remoteState.active_page ||
              prev.activeTab,
            filters: {
              ...prev.filters,
              ...(remoteState.filters || {}),
            },
            selectedFindingId:
              remoteState.preferences?.selected_finding_id ??
              remoteState.selectedFindingId ??
              remoteState.selected_finding_id ??
              prev.selectedFindingId,
            activityLog:
              Array.isArray(remoteState.activityLog) &&
              remoteState.activityLog.length > 0
                ? remoteState.activityLog.slice(0, MAX_ACTIVITY_LOG)
                : Array.isArray(remoteState.recent_actions) &&
                  remoteState.recent_actions.length > 0
                ? remoteState.recent_actions.slice(0, MAX_ACTIVITY_LOG)
                : prev.activityLog,
            copilotByWorkspace: (() => {
              const remoteCopilot =
                remoteState.copilot_context?.by_workspace ||
                remoteState.copilot_context?.copilotByWorkspace ||
                remoteState.copilotByWorkspace;
              return remoteCopilot && typeof remoteCopilot === "object"
                ? { ...prev.copilotByWorkspace, ...remoteCopilot }
                : prev.copilotByWorkspace;
            })(),
          };
          writeStoredMemory(merged);
          return merged;
        });
        setSyncStatus("synced");
        hasHydratedRemoteRef.current = true;
      })
      .catch(() => {
        if (!cancelled) {
          setSyncStatus("local-only");
          hasHydratedRemoteRef.current = true;
        }
      });

    return () => {
      cancelled = true;
    };
  }, []); // Run once on mount

  // Persist to localStorage immediately & debounce PUT /api/account/memory
  useEffect(() => {
    writeStoredMemory(memory);

    if (typeof api.putAccountMemory !== "function") {
      return undefined;
    }

    if (syncTimerRef.current) {
      clearTimeout(syncTimerRef.current);
    }

    syncTimerRef.current = setTimeout(() => {
      const accountId = memory.profile?.account_id || DEFAULT_PROFILE.account_id;
      const workspaceId = memory.activeWorkspaceId || "default";
      api
        .putAccountMemory({
          account_id: accountId,
          workspace_id: workspaceId,
          user_name: memory.profile?.name || DEFAULT_PROFILE.name,
          user_role: memory.profile?.role || DEFAULT_PROFILE.role,
          active_page: memory.activeTab,
          active_tab: memory.activeTab,
          filters: memory.filters,
          recent_actions: memory.activityLog,
          copilot_context: {
            by_workspace: memory.copilotByWorkspace || {},
          },
          preferences: {
            selected_finding_id: memory.selectedFindingId || null,
          },
        })
        .then(() => setSyncStatus("synced"))
        .catch(() => setSyncStatus("local-only"));
    }, 600);

    return () => {
      if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    };
  }, [memory]);

  const updateProfile = useCallback((partial) => {
    setMemory((prev) => ({
      ...prev,
      profile: {
        ...prev.profile,
        ...partial,
      },
    }));
  }, []);

  const setActiveWorkspaceId = useCallback((workspaceId) => {
    setMemory((prev) => ({
      ...prev,
      activeWorkspaceId: workspaceId || "default",
    }));
  }, []);

  const setActiveTab = useCallback((tab) => {
    setMemory((prev) => ({
      ...prev,
      activeTab: tab || "exceptions",
    }));
  }, []);

  const setFilters = useCallback((updater) => {
    setMemory((prev) => {
      const nextFilters =
        typeof updater === "function" ? updater(prev.filters) : { ...prev.filters, ...updater };
      return {
        ...prev,
        filters: {
          ...DEFAULT_FILTERS,
          ...nextFilters,
        },
      };
    });
  }, []);

  const resetFilters = useCallback(() => {
    setMemory((prev) => ({
      ...prev,
      filters: DEFAULT_FILTERS,
    }));
  }, []);

  const setSelectedFindingId = useCallback((findingId) => {
    setMemory((prev) => ({
      ...prev,
      selectedFindingId: findingId || null,
    }));
  }, []);

  const recordPageActivity = useCallback((page, action, detail = "") => {
    const entry = {
      id: `act-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      page,
      action,
      detail,
      timestamp: new Date().toISOString(),
    };
    setMemory((prev) => ({
      ...prev,
      activityLog: [entry, ...(prev.activityLog || [])].slice(0, MAX_ACTIVITY_LOG),
    }));
  }, []);

  const appendCopilotMessage = useCallback((workspaceId, entry) => {
    const ws = workspaceId || "default";
    setMemory((prev) => {
      const existing = prev.copilotByWorkspace?.[ws] || [];
      const nextList = [...existing, entry].slice(-MAX_COPILOT_HISTORY);
      return {
        ...prev,
        copilotByWorkspace: {
          ...(prev.copilotByWorkspace || {}),
          [ws]: nextList,
        },
      };
    });
  }, []);

  const clearCopilotHistory = useCallback((workspaceId) => {
    const ws = workspaceId || "default";
    setMemory((prev) => ({
      ...prev,
      copilotByWorkspace: {
        ...(prev.copilotByWorkspace || {}),
        [ws]: [],
      },
    }));
  }, []);

  const value = useMemo(() => {
    const wsId = memory.activeWorkspaceId || "default";
    return {
      profile: memory.profile || DEFAULT_PROFILE,
      reviewerLabel: formatReviewerLabel(memory.profile),
      updateProfile,
      activeWorkspaceId: wsId,
      setActiveWorkspaceId,
      activeTab: memory.activeTab || "exceptions",
      setActiveTab,
      filters: memory.filters || DEFAULT_FILTERS,
      setFilters,
      resetFilters,
      selectedFindingId: memory.selectedFindingId || null,
      setSelectedFindingId,
      activityLog: memory.activityLog || [],
      recordPageActivity,
      copilotHistory: memory.copilotByWorkspace?.[wsId] || [],
      getCopilotHistoryForWorkspace: (ws) =>
        memory.copilotByWorkspace?.[ws || "default"] || [],
      appendCopilotMessage,
      clearCopilotHistory,
      syncStatus,
    };
  }, [
    memory,
    syncStatus,
    updateProfile,
    setActiveWorkspaceId,
    setActiveTab,
    setFilters,
    resetFilters,
    setSelectedFindingId,
    recordPageActivity,
    appendCopilotMessage,
    clearCopilotHistory,
  ]);

  return (
    <AccountMemoryContext.Provider value={value}>
      {children}
    </AccountMemoryContext.Provider>
  );
}

const FALLBACK_CONTEXT = {
  profile: DEFAULT_PROFILE,
  reviewerLabel: formatReviewerLabel(DEFAULT_PROFILE),
  updateProfile: () => {},
  activeWorkspaceId: "default",
  setActiveWorkspaceId: () => {},
  activeTab: "exceptions",
  setActiveTab: () => {},
  filters: DEFAULT_FILTERS,
  setFilters: () => {},
  resetFilters: () => {},
  selectedFindingId: null,
  setSelectedFindingId: () => {},
  activityLog: [],
  recordPageActivity: () => {},
  copilotHistory: [],
  getCopilotHistoryForWorkspace: () => [],
  appendCopilotMessage: () => {},
  clearCopilotHistory: () => {},
  syncStatus: "local-only",
};

export function useAccountMemory() {
  const ctx = useContext(AccountMemoryContext);
  return ctx || FALLBACK_CONTEXT;
}
