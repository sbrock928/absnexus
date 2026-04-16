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
import type { DagNodeData } from "./types";
import styles from "./DagGraphView.module.css";

const NODE_TYPE_MAP: Record<string, string> = {
  input: "inputNode",
  calculation: "calcNode",
  distribution: "distNode",
  validation: "validationNode",
};

const nodeTypes: NodeTypes = {
  inputNode: InputNode,
  calcNode: CalcNode,
  distNode: DistNode,
  validationNode: ValidationNode,
};

interface Props {
  backendNodes: any[];
  backendEdges: any[];
  stream: string;
  onCreateNode: (type: string, position: { x: number; y: number }) => Promise<any>;
  onUpdateNode: (nodeId: number, fields: Record<string, any>) => Promise<void>;
  onDeleteNode: (nodeId: number) => Promise<void>;
  onDeactivateNode: (nodeId: number) => Promise<void>;
  onReactivateNode: (nodeId: number) => Promise<void>;
  onCreateEdge: (sourceId: number, targetId: number) => Promise<void>;
  onDeleteEdge: (edgeId: number) => Promise<void>;
}

function buildRfNodes(backendNodes: any[], stream: string): Node[] {
  return backendNodes
    .filter((n) => n.stream === stream)
    .map((n) => ({
      id: String(n.id),
      type: NODE_TYPE_MAP[n.node_type] ?? "calcNode",
      position: { x: n.position_x ?? 0, y: n.position_y ?? 0 },
      data: {
        label: n.name,
        node_key: n.node_key,
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
        comparison_var: n.comparison_var,
        payment_type: n.payment_type,
        backendId: n.id,
      } as DagNodeData,
    }));
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
      style: { stroke: "var(--text-muted)", strokeWidth: 1.5 },
    }));
}

export function DagGraphView({
  backendNodes,
  backendEdges,
  stream,
  onCreateNode,
  onUpdateNode,
  onDeleteNode,
  onDeactivateNode,
  onReactivateNode,
  onCreateEdge,
  onDeleteEdge,
}: Props) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const filteredBackendNodes = backendNodes.filter((n) => n.stream === stream);
  const visibleNodeIds = new Set(filteredBackendNodes.map((n) => n.id));

  const initialNodes = useMemo(
    () => buildRfNodes(backendNodes, stream),
    [backendNodes, stream]
  );
  const initialEdges = useMemo(
    () => buildRfEdges(backendEdges, visibleNodeIds),
    [backendEdges, visibleNodeIds]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync React Flow state when backend data changes
  useEffect(() => {
    setNodes(buildRfNodes(backendNodes, stream));
    setEdges(buildRfEdges(backendEdges, visibleNodeIds));
  }, [backendNodes, backendEdges, stream]);

  // Handle new connection between nodes
  const onConnect = useCallback(
    async (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      await onCreateEdge(Number(connection.source), Number(connection.target));
    },
    [onCreateEdge]
  );

  // Save position on drag end
  const onNodeDragStop = useCallback(
    (_: any, node: Node) => {
      onUpdateNode(Number(node.id), {
        position_x: node.position.x,
        position_y: node.position.y,
      });
    },
    [onUpdateNode]
  );

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
    const y = 100 + filteredBackendNodes.length * 80;
    await onCreateNode(type, { x, y });
  };

  // Look up selected node from BACKEND data (stable, not React Flow state)
  const selectedBackend = selectedNodeId
    ? backendNodes.find((n) => String(n.id) === selectedNodeId)
    : null;

  const selectedData: DagNodeData | undefined = selectedBackend
    ? {
        label: selectedBackend.name,
        node_key: selectedBackend.node_key,
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
        comparison_var: selectedBackend.comparison_var,
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
          return src?.node_key ?? `node_${e.source_node_id}`;
        })
    : [];

  const downstream = selectedNodeId
    ? backendEdges
        .filter((e) => String(e.source_node_id) === selectedNodeId)
        .map((e) => {
          const tgt = backendNodes.find((n) => n.id === e.target_node_id);
          return tgt?.node_key ?? `node_${e.target_node_id}`;
        })
    : [];

  return (
    <div className={styles.layout}>
      <NodePalette onAddNode={handleAddNode} />

      <div className={styles.canvas}>
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
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--border-color)" gap={20} size={1} />
          <Controls />
          <MiniMap
            style={{ background: "var(--bg-sidebar)" }}
            nodeColor={(n) => {
              const type = (n.data as DagNodeData)?.node_type;
              if (type === "input") return "#4ade80";
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
              backendFields.comparison_var = fields.comparison_var || null;
            if (fields.payment_type !== undefined)
              backendFields.payment_type = fields.payment_type || null;
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
        />
      ) : (
        <div className={styles.emptyPanel}>
          Click a node to view its properties.
        </div>
      )}
    </div>
  );
}
