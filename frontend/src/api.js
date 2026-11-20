/**
 * LedgerLens API Client
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      ...(options.isFormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
    ...options,
  });

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

  uploadDocument: (kind, file) => {
    const formData = new FormData();
    formData.append("kind", kind);
    formData.append("file", file);
    return request("/api/ingest/upload", {
      method: "POST",
      body: formData,
      isFormData: true,
    });
  },

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
};
