/**
 * LedgerLens API Client
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const { timeoutMs = 15000, isFormData, headers, ...fetchOptions } = options;
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;

  let response;
  try {
    response = await fetch(url, {
      ...fetchOptions,
      signal: controller ? controller.signal : undefined,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...headers,
      },
    });
  } catch (err) {
    if (err?.name === "AbortError") {
      throw new Error("Request timed out. Please retry.");
    }
    throw err;
  } finally {
    if (timer) clearTimeout(timer);
  }

  if (!response.ok) {
    let errorDetail = `Request failed: ${response.statusText}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  getHealth: () => request("/health"),

  getStats: () => request("/api/stats"),

  getBatches: () => request("/api/batches"),

  getFindings: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status && filters.status !== "all") params.append("status", filters.status);
    if (filters.severity && filters.severity !== "all") params.append("severity", filters.severity);
    if (filters.rule_id && filters.rule_id !== "all") params.append("rule_id", filters.rule_id);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request(`/api/findings${qs}`);
  },

  getFinding: (id) => request(`/api/findings/${id}`),

  postDecision: (findingId, action, reviewer, note = "") =>
    request(`/api/findings/${findingId}/decision`, {
      method: "POST",
      body: JSON.stringify({ action, reviewer, note }),
    }),

  postBulkDecision: (findingIds, action, reviewer, note = "") =>
    request("/api/findings/bulk-decision", {
      method: "POST",
      body: JSON.stringify({ finding_ids: findingIds, action, reviewer, note }),
    }),

  getDisputePacket: (findingId) =>
    request(`/api/findings/${findingId}/dispute-packet`),

  uploadDocument: (kind, file, autoRun = true) => {
    const formData = new FormData();
    formData.append("kind", kind);
    formData.append("file", file);
    formData.append("auto_run", String(Boolean(autoRun)));
    const qs = autoRun ? "?auto_run=true" : "?auto_run=false";
    return request(`/api/ingest/upload${qs}`, {
      method: "POST",
      body: formData,
      isFormData: true,
    });
  },

  runPayrunSweep: (workspaceId = "default") =>
    request(`/api/jobs/payrun-sweep?workspace_id=${encodeURIComponent(workspaceId || "default")}`, {
      method: "POST",
    }),

  runExtract: (batchId) =>
    request(`/api/run/${batchId}/extract`, {
      method: "POST",
    }),

  runDetect: (batchId) =>
    request(`/api/run/${batchId}/detect`, {
      method: "POST",
    }),

  runGlobalDetect: () =>
    request("/api/run-detection", {
      method: "POST",
    }),

  seedSampleData: () =>
    request("/api/seed/sample_data", {
      method: "POST",
    }),

  getMemo: () => request("/api/memo"),

  getAuditLog: () => request("/api/audit-log"),

  getGcpStatus: () => request("/api/gcp/status"),

  syncBigQuery: () =>
    request("/api/gcp/bigquery/sync", {
      method: "POST",
    }),

  getExecutiveAnalytics: () => request("/api/analytics/executive"),

  getPolicy: () => request("/api/policy"),

  updatePolicy: (updates) =>
    request("/api/policy", {
      method: "PUT",
      body: JSON.stringify(updates),
    }),

  getExportCsvUrl: () => `${API_BASE}/api/export/findings.csv`,

  // ---- Embedded knowledge graph (LadybugDB) ----

  getGraphStats: () => request("/api/graph/stats"),

  rebuildGraph: (batchId) =>
    request(`/api/graph/rebuild${batchId ? `?batch_id=${encodeURIComponent(batchId)}` : ""}`, {
      method: "POST",
    }),

  getFindingSubgraph: (findingId) =>
    request(`/api/graph/findings/${encodeURIComponent(findingId)}/subgraph`),

  getEntityNeighborhood: (entityType, entityId, hops = 2) =>
    request(
      `/api/graph/entity/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}?hops=${hops}`,
    ),

  // ---- Batch records, workspaces & copilot ----

  updateBatchRecords: (batchId, payload) =>
    request(`/api/batches/${batchId}/records`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  getBatchFileUrl: (batchId) => `${API_BASE}/api/batches/${batchId}/file`,

  getWorkspaces: () => request("/api/workspaces"),

  createWorkspace: (payload) =>
    request("/api/workspaces", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  askCopilot: (question, workspaceId = "default", context = {}) => {
    const body = {
      question,
      workspace_id: workspaceId,
    };
    if (context?.currentPage) body.current_page = context.currentPage;
    if (context?.selectedFindingId) body.selected_finding_id = context.selectedFindingId;
    if (context?.selectedFinding) body.selected_finding = context.selectedFinding;
    if (Array.isArray(context?.conversationHistory) && context.conversationHistory.length > 0) {
      body.conversation_history = context.conversationHistory;
    }
    return request("/api/copilot/ask", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  getAccountMemory: (accountId = "default-user", workspaceId = "default") =>
    request(
      `/api/account/memory?account_id=${encodeURIComponent(accountId)}&workspace_id=${encodeURIComponent(workspaceId)}`,
      { timeoutMs: 5000 }
    ),

  putAccountMemory: (payload) =>
    request("/api/account/memory", {
      method: "PUT",
      body: JSON.stringify(payload),
      timeoutMs: 5000,
    }),

  verifyAuditChain: () => request("/api/audit-log/verify"),
};
