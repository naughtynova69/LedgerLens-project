import React, { useCallback, useEffect, useState } from "react";
import { Network, RefreshCw } from "lucide-react";
import { api } from "../api";

/**
 * Knowledge-graph status strip (LadybugDB): single-line 36px institutional
 * bar showing entity/link counts, multi-hop risks (R6-R8), and sync action.
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
    <div className="min-h-[36px] px-3 py-1.5 rounded-md bg-[#F8FAFC] border border-[#E2E8F0] flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2 text-xs font-mono tabular-nums text-slate-600 min-w-0">
        <Network className="w-3.5 h-3.5 text-slate-500 shrink-0" />
        {loadError ? (
          <span className="truncate">
            Graph: unavailable (set <code className="text-slate-800">LEDGERLENS_GRAPH_ENABLED=true</code>)
          </span>
        ) : !graphStats ? (
          <span>Graph: loading…</span>
        ) : (
          <span className="truncate">
            Graph:{" "}
            <span className="font-semibold text-slate-900">
              {graphStats.total_nodes ?? 0}
            </span>{" "}
            entities ·{" "}
            <span className="font-semibold text-slate-900">
              {graphStats.total_relationships ?? 0}
            </span>{" "}
            links ·{" "}
            <span className="font-semibold text-slate-900">
              {graphStats.multi_hop_risks ?? 0}
            </span>{" "}
            multi-hop risks
          </span>
        )}
      </div>

      <button
        type="button"
        onClick={handleRebuild}
        disabled={rebuilding}
        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-[#E2E8F0] bg-white hover:bg-slate-100 text-[11px] font-medium text-slate-700 transition-colors disabled:opacity-50 shrink-0"
        title="Rebuild the graph projection from the relational system of record"
      >
        <RefreshCw className={`w-3 h-3 text-slate-500 ${rebuilding ? "animate-spin" : ""}`} />
        <span>{rebuilding ? "Syncing…" : "Sync"}</span>
      </button>
    </div>
  );
}
