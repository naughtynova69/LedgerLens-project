import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";

const NODE_COLORS = {
  Invoice: "#0F172A",
  Vendor: "#334155",
  BankAccount: "#B45309",
  TaxIdentifier: "#475569",
  Address: "#64748B",
  Approver: "#475569",
  Contract: "#047857",
  PurchaseOrder: "#0F766E",
  InvoiceLine: "#64748B",
  Payment: "#047857",
  CreditNote: "#B91C1C",
};

const RISK_EDGE_TYPES = new Set([
  "USES_BANK",
  "HAS_TAX_ID",
  "LOCATED_AT",
  "APPROVER_LOCATED_AT",
  "APPROVER_USES_BANK",
  "AMENDS",
  "ISSUED_CREDIT",
  "APPROVED_INVOICE",
]);

/**
 * Interactive evidence-subgraph renderer (pure SVG — zero extra dependencies).
 *
 * Layered left-to-right layout computed with a BFS depth assignment from the
 * highest-priority root node, click-to-inspect node details, drag-to-pan,
 * wheel/button zoom, institutional slate entity coding, and amber risk edges.
 */
export function EvidenceGraphCanvas({ findingId, subgraph: providedSubgraph, height = 320 }) {
  const [subgraph, setSubgraph] = useState(providedSubgraph || null);
  const [status, setStatus] = useState(providedSubgraph ? "ready" : "loading");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  const [transform, setTransform] = useState({ x: 40, y: 40, k: 1 });
  const dragState = useRef(null);
  const svgRef = useRef(null);

  useEffect(() => {
    if (providedSubgraph) {
      setSubgraph(providedSubgraph);
      setStatus("ready");
      return;
    }
    if (!findingId) return;
    let cancelled = false;
    setStatus("loading");
    api
      .getFindingSubgraph(findingId)
      .then((data) => {
        if (cancelled) return;
        setSubgraph(data);
        setStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message || "Failed to load evidence subgraph.");
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [findingId, providedSubgraph]);

  const layout = useMemo(() => {
    if (!subgraph || !Array.isArray(subgraph.nodes) || subgraph.nodes.length === 0) return null;
    const nodes = subgraph.nodes.map((n) => ({ ...n }));
    const edges = subgraph.edges || [];

    const adjacency = new Map();
    edges.forEach((e) => {
      if (!adjacency.has(e.source)) adjacency.set(e.source, []);
      if (!adjacency.has(e.target)) adjacency.set(e.target, []);
      adjacency.get(e.source).push(e.target);
      adjacency.get(e.target).push(e.source);
    });

    // BFS depth from the first highlighted node (or first node) → column index.
    const roots = nodes.filter((n) => n.highlight);
    const rootNode = roots[0] || nodes[0];
    const depth = new Map([[rootNode.id, 0]]);
    const queue = [rootNode.id];
    while (queue.length > 0) {
      const current = queue.shift();
      for (const next of adjacency.get(current) || []) {
        if (!depth.has(next)) {
          depth.set(next, depth.get(current) + 1);
          queue.push(next);
        }
      }
    }
    const maxDepth = Math.max(0, ...Array.from(depth.values()));
    // Unreachable nodes get trailing columns.
    let fallbackDepth = maxDepth + 1;
    nodes.forEach((n) => {
      if (!depth.has(n.id)) depth.set(n.id, fallbackDepth++);
    });

    const COLUMN_WIDTH = 210;
    const ROW_HEIGHT = 86;
    const byColumn = new Map();
    nodes.forEach((n) => {
      const col = depth.get(n.id);
      if (!byColumn.has(col)) byColumn.set(col, []);
      byColumn.get(col).push(n);
    });

    const positioned = new Map();
    let maxRows = 0;
    Array.from(byColumn.keys())
      .sort((a, b) => a - b)
      .forEach((col) => {
        const columnNodes = byColumn.get(col);
        maxRows = Math.max(maxRows, columnNodes.length);
        columnNodes.forEach((n, row) => {
          positioned.set(n.id, {
            ...n,
            x: 90 + col * COLUMN_WIDTH,
            y: 60 + row * ROW_HEIGHT,
            depth: col,
          });
        });
      });

    const width = 180 + Math.max(0, maxDepth) * COLUMN_WIDTH + (fallbackDepth > maxDepth + 1 ? COLUMN_WIDTH : 0);
    return {
      nodes: positioned,
      edges,
      width: Math.max(width, 560),
      height: 120 + maxRows * ROW_HEIGHT,
    };
  }, [subgraph]);

  const onWheel = useCallback((event) => {
    event.preventDefault();
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    setTransform((t) => ({
      ...t,
      k: Math.min(2.5, Math.max(0.4, t.k * factor)),
    }));
  }, []);

  const onMouseDown = (event) => {
    dragState.current = { x: event.clientX, y: event.clientY, tx: transform.x, ty: transform.y };
  };
  const onMouseMove = (event) => {
    if (!dragState.current) return;
    setTransform((t) => ({
      ...t,
      x: dragState.current.tx + (event.clientX - dragState.current.x),
      y: dragState.current.ty + (event.clientY - dragState.current.y),
    }));
  };
  const endDrag = () => {
    dragState.current = null;
  };

  if (status === "loading") {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center bg-[#F8FAFC] border border-[#E2E8F0] rounded-md text-xs text-slate-500 font-mono"
      >
        Loading evidence subgraph…
      </div>
    );
  }

  if (status === "error") {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center bg-red-50/40 border border-red-200 rounded-md text-xs text-[#B91C1C]"
      >
        {error}
      </div>
    );
  }

  if (!layout) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center bg-[#F8FAFC] border border-[#E2E8F0] rounded-md text-xs text-slate-500"
      >
        No graph evidence available for this finding.
      </div>
    );
  }

  const { nodes, edges } = layout;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono tabular-nums text-slate-500">
          <span className="px-1.5 py-0.5 rounded bg-[#F8FAFC] border border-[#E2E8F0] text-slate-700">
            {subgraph.cypher_rule || "GRAPH"}
          </span>
          <span>{nodes.size} entities</span>
          <span>·</span>
          <span>{edges.length} links</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Zoom out"
            onClick={() => setTransform((t) => ({ ...t, k: Math.max(0.4, t.k * 0.85) }))}
            className="px-2 py-0.5 rounded border border-[#E2E8F0] text-xs text-slate-900 bg-white hover:bg-slate-50 transition-colors"
          >
            −
          </button>
          <button
            type="button"
            aria-label="Reset view"
            onClick={() => setTransform({ x: 40, y: 40, k: 1 })}
            className="px-2 py-0.5 rounded border border-[#E2E8F0] text-xs text-slate-900 bg-white hover:bg-slate-50 transition-colors"
          >
            Reset
          </button>
          <button
            type="button"
            aria-label="Zoom in"
            onClick={() => setTransform((t) => ({ ...t, k: Math.min(2.5, t.k * 1.15) }))}
            className="px-2 py-0.5 rounded border border-[#E2E8F0] text-xs text-slate-900 bg-white hover:bg-slate-50 transition-colors"
          >
            +
          </button>
        </div>
      </div>

      <div
        className="relative bg-[#F8FAFC] border border-[#E2E8F0] rounded-md overflow-hidden cursor-grab active:cursor-grabbing"
        style={{ height }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
      >
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          onWheel={onWheel}
          role="img"
          aria-label="Evidence subgraph"
        >
          <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
            {edges.map((edge, idx) => {
              const s = nodes.get(edge.source);
              const t = nodes.get(edge.target);
              if (!s || !t) return null;
              const isRisk =
                (s.highlight && t.highlight) ||
                RISK_EDGE_TYPES.has(edge.type) ||
                subgraph.edges?.some(
                  (e) => e.source === edge.source && e.target === edge.target && e.properties?.risk
                );
              const mx = (s.x + t.x) / 2;
              const my = (s.y + t.y) / 2;
              return (
                <g key={`e-${idx}`}>
                  <line
                    x1={s.x}
                    y1={s.y}
                    x2={t.x}
                    y2={t.y}
                    stroke={isRisk ? "#B45309" : "#94A3B8"}
                    strokeWidth={isRisk ? 2 : 1}
                    strokeDasharray={isRisk ? "none" : "4 3"}
                    opacity={isRisk ? 0.9 : 0.6}
                  />
                  <text
                    x={mx}
                    y={my - 4}
                    textAnchor="middle"
                    fontSize="8"
                    fill={isRisk ? "#B45309" : "#64748B"}
                    fontFamily="ui-monospace, monospace"
                  >
                    {edge.type}
                  </text>
                </g>
              );
            })}

            {Array.from(nodes.values()).map((node) => {
              const color = NODE_COLORS[node.type] || "#475569";
              const r = node.highlight ? 16 : 12;
              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x},${node.y})`}
                  onClick={() => setSelected(node)}
                  className="cursor-pointer"
                >
                  {node.highlight && (
                    <circle r={r + 5} fill="none" stroke={color} strokeWidth="1.5" opacity="0.3" />
                  )}
                  <circle
                    r={r}
                    fill="#FFFFFF"
                    stroke={color}
                    strokeWidth={node.highlight ? 2.5 : 1.5}
                  />
                  <circle r="4.5" fill={color} />
                  <text
                    y={r + 12}
                    textAnchor="middle"
                    fontSize="9.5"
                    fill="#0F172A"
                    fontFamily="ui-monospace, monospace"
                    fontWeight={node.highlight ? 600 : 400}
                  >
                    {node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {selected && (
        <div className="p-3 rounded-md bg-white border border-[#E2E8F0] text-xs space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="inline-block w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: NODE_COLORS[selected.type] || "#475569" }}
              />
              <span className="font-mono font-medium text-slate-900 truncate">{selected.id}</span>
              <span className="text-slate-500">({selected.type})</span>
            </div>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-[11px] text-slate-500 hover:text-slate-900"
            >
              Close
            </button>
          </div>
          {subgraph.summary && (
            <p className="text-slate-600 leading-relaxed">
              <span className="font-medium text-slate-900">Path:</span> {subgraph.summary}
            </p>
          )}
          {Object.entries(selected.properties || {}).length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[11px] text-slate-500">
              {Object.entries(selected.properties)
                .filter(([key]) => key !== "_LABEL")
                .map(([key, value]) => (
                  <span key={key}>
                    <span>{key}=</span>
                    <span className="text-slate-900">{String(value)}</span>
                  </span>
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
