import React, { useCallback, useEffect, useState } from "react";
import { Network, RefreshCw } from "lucide-react";
import { api } from "../api";

/**
 * Knowledge-graph KPI card (LadybugDB): entity/link counts, multi-hop risk
 * findings (R6-R8), and a one-click deterministic rebuild/sync action.
 */
export function GraphStatsCard({ onToast }) {
  const [graphStats, setGraphStats] = useState(null);
  const [rebuilding, setRebuilding] = useState(false);
  const [loadError, setLoadError] = useState("");

  const loadStats = useCallback(() => {
    api
      .getGraphStats()
      .then((data) => {
        setGraphStats(data);
        setLoadError("");
      })
      .catch((err) => setLoadError(err.message || "Graph engine unavailable."));
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleRebuild = async () => {
    setRebuilding(true);
    try {
      const result = await api.rebuildGraph();
      setGraphStats((prev) => ({
        ...(prev || {}),
        nodes: result.nodes || prev?.nodes,
        relationships: result.relationships || prev?.relationships,
        total_nodes: result.total_nodes,
        total_relationships: result.total_relationships,
        multi_hop_risks: prev?.multi_hop_risks,
      }));
      if (onToast) {
        onToast(
          `Graph rebuilt: ${result.total_nodes} entities, ${result.total_relationships} links in ${result.duration_ms} ms.`,
          "success",
          "Knowledge Graph Synced"
        );
      }
    } catch (err) {
      if (onToast) {
        onToast(err.message || "Graph rebuild failed.", "error", "Graph Rebuild Failed");
      }
    } finally {
      setRebuilding(false);
    }
  };

  return (
    <div className="p-4 rounded-lg bg-white border border-gray-200 space-y-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#111827]">
          <Network className="w-4 h-4 text-[#4F46E5]" />
          <span>Knowledge Graph (LadybugDB)</span>
        </div>
        <button
          type="button"
          onClick={handleRebuild}
          disabled={rebuilding}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-gray-200 text-xs font-medium text-gray-700 bg-white hover:bg-gray-50 transition-colors disabled:opacity-50"
          title="Rebuild the graph projection from the relational system of record"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${rebuilding ? "animate-spin" : ""}`} />
          {rebuilding ? "Syncing…" : "Rebuild / Sync"}
        </button>
      </div>

      {loadError ? (
        <p className="text-xs text-slate-500">
          Graph engine not enabled — set{" "}
          <code className="font-mono">LEDGERLENS_GRAPH_ENABLED=true</code> to activate R6–R8
          multi-hop detection.
        </p>
      ) : !graphStats ? (
        <p className="text-xs text-slate-500">Loading graph statistics…</p>
      ) : (
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
            <div className="text-lg font-bold font-mono tabular-nums text-slate-900">
              {graphStats.total_nodes ?? 0}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Entities</div>
          </div>
          <div className="p-2 rounded-lg bg-slate-50 border border-slate-200">
            <div className="text-lg font-bold font-mono tabular-nums text-slate-900">
              {graphStats.total_relationships ?? 0}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Links</div>
          </div>
          <div className="p-2 rounded-lg bg-[#EEF2FF] border border-[#C7D2FE]">
            <div className="text-lg font-bold font-mono tabular-nums text-[#4F46E5]">
              {graphStats.multi_hop_risks ?? 0}
            </div>
            <div className="text-[10px] uppercase tracking-wider text-[#4F46E5]/80">Multi-hop</div>
          </div>
        </div>
      )}
    </div>
  );
}
