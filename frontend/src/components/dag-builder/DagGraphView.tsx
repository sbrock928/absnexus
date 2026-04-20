import { useCallback, useState, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { InputNode } from "./InputNode";
import { CalcNode } from "./CalcNode";
import { DistNode } from "./DistNode";
import { ValidationNode } from "./ValidationNode";
import { NodePalette } from "./NodePalette";
import { NodePropertiesPanel } from "./NodePropertiesPanel";
import { layoutDag } from "./autoLayout";
import type { DagNodeData } from "./types";
import styles from "./DagGraphView.module.css";

const NODE_TYPE_MAP: Record<string, string> = {
  input: "inputNode",
  input_value: "inputNode",
  calculation: "calcNode",
  distribution: "distNode",
  validation: "validationNode",
};

// Tier layout — nodes are stacked into three horizontal bands so the graph
// reads top-down as "Outputs → Calcs → Inputs" regardless of saved positions.
// Position_x (horizontal) is still driven by autoLayout / user drag.
export type TierKey = "top" | "mid" | "bot";

export const NODE_TYPE_TIER: Record<string, TierKey> = {
  distribution: "top",
  validation: "top",
  calculation: "mid",
  input: "bot",
  input_value: "bot",
};

const TIER_Y: Record<TierKey, number> = {
  top: 0,
  mid: 260,
  bot: 520,
};

const nodeTypes: NodeTypes = {
  inputNode: InputNode,
  calcNode: CalcNode,
  distNode: DistNode,
  validationNode: ValidationNode,
};

export interface FormulaToken {
  name: string;
  label: string;
  category: "variable" | "node" | "function";
}

interface Props {
  backendNodes: any[];
  backendEdges: any[];
  visibleNodeIds: Set<number>;
  availableTokens?: FormulaToken[];
  mappedVariables?: { id: number; name: string; display_name: string | null }[];
  onCreateNode: (type: string, position: { x: number; y: number }) => Promise<any>;
  onUpdateNode: (nodeId: number, fields: Record<string, any>) => Promise<void>;
  onDeleteNode: (nodeId: number) => Promise<void>;
  onDeactivateNode: (nodeId: number) => Promise<void>;
  onReactivateNode: (nodeId: number) => Promise<void>;
  onCreateEdge: (sourceId: number, targetId: number) => Promise<void>;
  onDeleteEdge: (edgeId: number) => Promise<void>;
}

function buildRfNodes(
  backendNodes: any[],
  visibleIds: Set<number>,
  backendEdges: any[],
  overrides: Map<string, { x: number; y: number }>,
): Node[] {
  const visible = backendNodes.filter((n) => visibleIds.has(n.id));
  // Compute layout from the current structure. Stored position_x is ignored
  // — the graph is always laid out top→bottom by topological rank so it
  // stays readable regardless of how the DAG has evolved. Individual nodes
  // can still be dragged; their new positions are stored in `overrides`
  // (cleared only by the Re-layout button).
  const layoutInputs = visible.map((n) => ({
    id: String(n.id),
    node_type: n.node_type,
  }));
  const layoutEdges = backendEdges.map((e) => ({
    source: String(e.source_node_id),
    target: String(e.target_node_id),
  }));
  const positions = layoutDag(layoutInputs, layoutEdges);

  return visible.map((n) => {
    const id = String(n.id);
    const override = overrides.get(id);
    const pos = override ?? positions.get(id) ?? { x: 0, y: 0 };
    return {
      id,
      type: NODE_TYPE_MAP[n.node_type] ?? "calcNode",
      position: pos,
      data: {
        label: n.name,
        node_key: n.key ?? n.node_key,
        node_type: n.node_type,
        stream: n.stream,
        is_active: n.is_active,
        formula: n.formula,
        input_source: n.input_source,
        cell_ref: n.variable_id ? `var #${n.variable_id}` : undefined,
        export_field: n.payment_type,
        tolerance: n.tolerance,
        description: n.description,
        variable_id: n.variable_id,
        tranche_field: n.tranche_field,
        default_prior_value: n.default_prior_value,
        comparison_var: n.comparison_variable ?? n.comparison_var,
        payment_type: n.payment_type,
        backendId: n.id,
      } as DagNodeData,
    };
  });
}

function buildRfEdges(backendEdges: any[], visibleNodeIds: Set<number>): Edge[] {
  return backendEdges
    .filter(
      (e) =>
        visibleNodeIds.has(e.source_node_id) &&
        visibleNodeIds.has(e.target_node_id)
    )
    .map((e) => ({
      id: String(e.id),
      source: String(e.source_node_id),
      target: String(e.target_node_id),
      animated: false,
      style: { stroke: "var(--text-muted)", strokeWidth: 1.5 },
      type: "smoothstep",
    }));
}

export function DagGraphView({
  backendNodes,
  backendEdges,
  visibleNodeIds,
  availableTokens = [],
  mappedVariables = [],
  onCreateNode,
  onUpdateNode,
  onDeleteNode,
  onDeactivateNode,
  onReactivateNode,
  onCreateEdge,
  onDeleteEdge,
}: Props) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  // Per-session drag overrides. Cleared when the user clicks "Re-layout".
  // Stored separately from the React Flow node state so we can distinguish
  // user intent ("I moved this") from auto-layout output.
  const [positionOverrides, setPositionOverrides] = useState<
    Map<string, { x: number; y: number }>
  >(new Map());

  const initialNodes = useMemo(
    () => buildRfNodes(backendNodes, visibleNodeIds, backendEdges, positionOverrides),
    [backendNodes, backendEdges, visibleNodeIds, positionOverrides]
  );
  const initialEdges = useMemo(
    () => buildRfEdges(backendEdges, visibleNodeIds),
    [backendEdges, visibleNodeIds]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync React Flow state when backend data changes
  useEffect(() => {
    setNodes(buildRfNodes(backendNodes, visibleNodeIds, backendEdges, positionOverrides));
    setEdges(buildRfEdges(backendEdges, visibleNodeIds));
  }, [backendNodes, backendEdges, visibleNodeIds, positionOverrides]);

  // Handle new connection between nodes
  const onConnect = useCallback(
    async (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      await onCreateEdge(Number(connection.source), Number(connection.target));
    },
    [onCreateEdge]
  );

  // Record the user's drag in the per-session override map. We also persist
  // to the backend (keeps the behaviour users expect when saving the DAG),
  // but the authoritative layout remains dagre — a full re-layout discards
  // every override at once.
  const onNodeDragStop = useCallback(
    (_: any, node: Node) => {
      setPositionOverrides((prev) => {
        const next = new Map(prev);
        next.set(node.id, { x: node.position.x, y: node.position.y });
        return next;
      });
      onUpdateNode(Number(node.id), {
        position_x: node.position.x,
      });
    },
    [onUpdateNode]
  );

  const relayout = useCallback(() => {
    setPositionOverrides(new Map());
  }, []);

  // Select node on click
  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  // Deselect on canvas click
  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  // Add node from palette
  const handleAddNode = async (type: string) => {
    const x = 200 + Math.random() * 200;
    const y = 100 + backendNodes.length * 80;
    await onCreateNode(type, { x, y });
  };

  // Look up selected node from BACKEND data (stable, not React Flow state)
  const selectedBackend = selectedNodeId
    ? backendNodes.find((n) => String(n.id) === selectedNodeId)
    : null;

  const selectedData: DagNodeData | undefined = selectedBackend
    ? {
        label: selectedBackend.name,
        node_key: selectedBackend.key ?? selectedBackend.node_key,
        node_type: selectedBackend.node_type,
        stream: selectedBackend.stream,
        is_active: selectedBackend.is_active,
        formula: selectedBackend.formula,
        input_source: selectedBackend.input_source,
        cell_ref: selectedBackend.variable_id
          ? `var #${selectedBackend.variable_id}`
          : undefined,
        export_field: selectedBackend.payment_type,
        tolerance: selectedBackend.tolerance,
        description: selectedBackend.description,
        variable_id: selectedBackend.variable_id,
        tranche_field: selectedBackend.tranche_field,
        default_prior_value: selectedBackend.default_prior_value,
        comparison_var: selectedBackend.comparison_variable ?? selectedBackend.comparison_var,
        payment_type: selectedBackend.payment_type,
        backendId: selectedBackend.id,
      }
    : undefined;

  // Compute dependencies and downstream for the selected node
  const deps = selectedNodeId
    ? backendEdges
        .filter((e) => String(e.target_node_id) === selectedNodeId)
        .map((e) => {
          const src = backendNodes.find((n) => n.id === e.source_node_id);
          return src ? `${src.name} (${src.key ?? src.node_key})` : `node_${e.source_node_id}`;
        })
    : [];

  const downstream = selectedNodeId
    ? backendEdges
        .filter((e) => String(e.source_node_id) === selectedNodeId)
        .map((e) => {
          const tgt = backendNodes.find((n) => n.id === e.target_node_id);
          return tgt ? `${tgt.name} (${tgt.key ?? tgt.node_key})` : `node_${e.target_node_id}`;
        })
    : [];

  return (
    <div className={styles.layout}>
      <NodePalette onAddNode={handleAddNode} />

      <div className={styles.canvas} style={{ position: "relative" }}>
        <button
          type="button"
          onClick={relayout}
          title="Re-layout — discards any manual drag positions and recomputes top-down"
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            zIndex: 10,
            padding: "6px 12px",
            fontSize: 12,
            fontWeight: 500,
            background: "var(--bg-secondary)",
            border: "1px solid var(--border, var(--border-color))",
            borderRadius: 6,
            color: "var(--text-primary)",
            cursor: "pointer",
            boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
          }}
        >
          ↻ Re-layout
          {positionOverrides.size > 0 && (
            <span style={{ marginLeft: 6, fontSize: 10, color: "var(--text-muted)" }}>
              ({positionOverrides.size} moved)
            </span>
          )}
        </button>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeDragStop={onNodeDragStop}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2, maxZoom: 1.2 }}
          minZoom={0.2}
          maxZoom={2}
          defaultEdgeOptions={{ type: "smoothstep" }}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--border-color)" gap={20} size={1} />
          <Controls />
          <MiniMap
            style={{ background: "var(--bg-sidebar)" }}
            nodeColor={(n) => {
              const type = (n.data as DagNodeData)?.node_type;
              if (type === "input" || type === "input_value") return "#4ade80";
              if (type === "calculation") return "#60a5fa";
              if (type === "distribution") return "#a78bfa";
              if (type === "validation") return "#fbbf24";
              return "#6b6b72";
            }}
          />
        </ReactFlow>
      </div>

      {selectedData ? (
        <NodePropertiesPanel
          node={selectedData}
          onUpdate={async (fields) => {
            // Map DagNodeData field names to backend field names
            const backendFields: Record<string, any> = {};
            if (fields.label !== undefined) backendFields.name = fields.label;
            if (fields.formula !== undefined) backendFields.formula = fields.formula;
            if (fields.description !== undefined) backendFields.description = fields.description;
            if (fields.default_prior_value !== undefined)
              backendFields.default_prior_value = fields.default_prior_value || null;
            if (fields.tolerance !== undefined)
              backendFields.tolerance = fields.tolerance || null;
            if (fields.comparison_var !== undefined)
              backendFields.comparison_variable = fields.comparison_var || null;
            if (fields.payment_type !== undefined) {
              // Keep payment_type (export templates) and export_field (waterfall) in sync.
              backendFields.payment_type = fields.payment_type || null;
              backendFields.export_field = fields.payment_type || null;
            }
            await onUpdateNode(selectedData.backendId, backendFields);
          }}
          onDelete={async () => {
            await onDeleteNode(selectedData.backendId);
            setSelectedNodeId(null);
          }}
          onDeactivate={async () => {
            await onDeactivateNode(selectedData.backendId);
          }}
          onReactivate={async () => {
            await onReactivateNode(selectedData.backendId);
          }}
          dependencies={deps}
          downstream={downstream}
          availableTokens={availableTokens}
          mappedVariables={mappedVariables}
        />
      ) : (
        <div className={styles.emptyPanel}>
          Click a node to view its properties.
        </div>
      )}
    </div>
  );
}
