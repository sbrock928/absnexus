import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { getLineage, type LineageResponse, type LineageNode } from "../../api/lineage";
import { fetchDag } from "../../api/dag";
import type { DagNode, DagEdge } from "../../api/dag";
import { LineageGraphNode, type LineageNodeData } from "./LineageGraphNode";
import { NODE_TYPE_TIER } from "../dag-builder/DagGraphView";

const TIER_Y: Record<string, number> = { top: 0, mid: 260, bot: 520 };

const nodeTypes: NodeTypes = {
  lineage: LineageGraphNode,
};

function fmt(v: string | null): string {
  if (v === null || v === undefined) return "—";
  const n = parseFloat(v);
  if (isNaN(n)) return v;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

interface Props {
  dealId: number;
  runId: number;
  nodeKey: string;
  onClose: () => void;
}

export function LineagePanel({ dealId, runId, nodeKey, onClose }: Props) {
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [dagNodes, setDagNodes] = useState<DagNode[]>([]);
  const [dagEdges, setDagEdges] = useState<DagEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getLineage(dealId, runId, nodeKey), fetchDag(dealId)])
      .then(([lin, dag]) => {
        if (cancelled) return;
        setLineage(lin);
        setDagNodes(dag.nodes);
        setDagEdges(dag.edges);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message || "Failed to load lineage");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dealId, runId, nodeKey]);

  const { rfNodes, rfEdges } = useMemo(() => {
    if (!lineage || dagNodes.length === 0) {
      return { rfNodes: [] as Node[], rfEdges: [] as Edge[] };
    }
    const valueByKey: Record<string, string | null> = {};
    const lineageByKey: Record<string, LineageNode> = {};
    for (const n of lineage.nodes) {
      valueByKey[n.node_key] = n.result;
      lineageByKey[n.node_key] = n;
    }
    const ancestorKeys = new Set(lineage.nodes.map((n) => n.node_key));
    const visibleBackend = dagNodes.filter((n) => ancestorKeys.has(n.key));
    const visibleIds = new Set(visibleBackend.map((n) => n.id));

    // If the target isn't a real DagNode (synthetic lineage for period-date
    // computations, deal constants, extracted tape vars, etc.), synthesize
    // the graph directly from the lineage response.
    if (visibleBackend.length === 0 && lineage.nodes.length > 0) {
      const synthNodes: Node[] = lineage.nodes.map((n, i) => ({
        id: `synth-${i}`,
        type: "lineage",
        position: { x: (i % 3) * 280, y: Math.floor(i / 3) * 180 },
        data: {
          name: n.node_name,
          node_key: n.node_key,
          node_type: n.node_type,
          value: n.result,
          formula: n.formula,
          is_target: n.node_key === lineage.target_node_key,
        } satisfies LineageNodeData,
      }));
      const keyToId: Record<string, string> = {};
      lineage.nodes.forEach((n, i) => {
        keyToId[n.node_key] = `synth-${i}`;
      });
      const synthEdges: Edge[] = [];
      lineage.nodes.forEach((n) => {
        for (const up of n.upstream_keys ?? []) {
          if (keyToId[up] && keyToId[n.node_key]) {
            synthEdges.push({
              id: `e-${up}-${n.node_key}`,
              source: keyToId[up],
              target: keyToId[n.node_key],
              type: "smoothstep",
              style: { stroke: "var(--text-muted)", strokeWidth: 1.5 },
            });
          }
        }
      });
      return { rfNodes: synthNodes, rfEdges: synthEdges };
    }

    const nodes: Node[] = visibleBackend.map((n) => ({
      id: String(n.id),
      type: "lineage",
      position: {
        x: n.position_x ?? 0,
        y: TIER_Y[NODE_TYPE_TIER[n.node_type] ?? "mid"],
      },
      data: {
        name: n.name,
        node_key: n.key,
        node_type: n.node_type,
        value: valueByKey[n.key] ?? null,
        formula: n.formula,
        is_target: n.key === lineage.target_node_key,
      } satisfies LineageNodeData,
    }));

    const edges: Edge[] = dagEdges
      .filter(
        (e) => visibleIds.has(e.source_node_id) && visibleIds.has(e.target_node_id),
      )
      .map((e) => ({
        id: String(e.id),
        source: String(e.source_node_id),
        target: String(e.target_node_id),
        animated: false,
        style: { stroke: "var(--text-muted)", strokeWidth: 1.5 },
        type: "smoothstep",
      }));

    return { rfNodes: nodes, rfEdges: edges };
  }, [lineage, dagNodes, dagEdges]);

  const targetNode = lineage?.nodes.find((n) => n.node_key === lineage?.target_node_key);

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: "min(900px, 75vw)",
        background: "var(--bg-primary)",
        borderLeft: "1px solid var(--border)",
        boxShadow: "-8px 0 24px rgba(0,0,0,0.3)",
        zIndex: 50,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 18px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
            Lineage
          </div>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>
            {lineage?.target_node_name ?? nodeKey}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
            <code>{nodeKey}</code>
            {lineage && ` · ${lineage.target_node_type} · ${lineage.lineage_count} nodes`}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {targetNode && (
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Result</div>
              <div style={{ fontSize: 18, fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                {fmt(lineage?.target_result ?? null)}
              </div>
              {targetNode.comparison_value !== null && (
                <div
                  style={{
                    fontSize: 11,
                    color: targetNode.validation_passed === false ? "var(--accent-red)" : "var(--text-muted)",
                    marginTop: 2,
                  }}
                >
                  Δ {fmt(targetNode.difference)} vs {fmt(targetNode.comparison_value)}
                </div>
              )}
            </div>
          )}
          <button
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            style={{ padding: "4px 10px" }}
          >
            Close
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ padding: 24, color: "var(--text-muted)" }}>Loading lineage…</div>
      )}
      {error && (
        <div style={{ padding: 24, color: "var(--accent-red)" }}>{error}</div>
      )}

      {!loading && !error && lineage && (
        <>
          {/* Filtered subgraph */}
          <div style={{ flex: "1 1 55%", minHeight: 300, borderBottom: "1px solid var(--border)" }}>
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2, maxZoom: 1.2 }}
              minZoom={0.2}
              maxZoom={2}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="var(--border-color)" gap={20} size={1} />
              <Controls showInteractive={false} />
              <MiniMap
                style={{ background: "var(--bg-sidebar)" }}
                nodeColor={(n) => {
                  const type = (n.data as LineageNodeData)?.node_type;
                  if (type === "input" || type === "input_value") return "#4ade80";
                  if (type === "calculation") return "#60a5fa";
                  if (type === "distribution") return "#a78bfa";
                  if (type === "validation") return "#fbbf24";
                  return "#6b6b72";
                }}
              />
            </ReactFlow>
          </div>

          {/* Ancestor table */}
          <div style={{ flex: "1 1 45%", overflow: "auto", padding: "12px 18px" }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
              Execution order
            </div>
            <table className="table" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Node</th>
                  <th>Formula → resolved</th>
                  <th style={{ textAlign: "right" }}>Result</th>
                </tr>
              </thead>
              <tbody>
                {[...lineage.nodes]
                  .sort((a, b) => (a.execution_order ?? 0) - (b.execution_order ?? 0))
                  .map((n) => (
                    <tr key={n.node_key}>
                      <td style={{ color: "var(--text-muted)" }}>{n.execution_order ?? "—"}</td>
                      <td>
                        <div style={{ fontWeight: 500 }}>{n.node_name}</div>
                        <div style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                          {n.node_key} · {n.node_type}
                          {n.cell_ref && ` · ${n.cell_ref}`}
                        </div>
                      </td>
                      <td>
                        {n.formula ? (
                          <>
                            <code style={{ fontSize: 11 }}>{n.formula}</code>
                            {n.formula_resolved && (
                              <div style={{ fontSize: 11, color: "var(--accent-green)", fontFamily: "var(--font-mono)" }}>
                                {n.formula_resolved}
                              </div>
                            )}
                          </>
                        ) : (
                          <span style={{ color: "var(--text-muted)" }}>—</span>
                        )}
                        {n.suspect_reason && (
                          <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4, fontStyle: "italic" }}>
                            {n.suspect_reason}
                          </div>
                        )}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                        {fmt(n.result)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
