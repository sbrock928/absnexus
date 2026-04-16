import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { DagNodeData } from "./types";

export function CalcNode({ data, selected }: NodeProps) {
  const d = data as DagNodeData;
  return (
    <div
      style={{
        background: "var(--bg-card)",
        borderTop: selected ? "2px solid #60a5fa" : "1px solid var(--border-color)",
        borderRight: selected ? "2px solid #60a5fa" : "1px solid var(--border-color)",
        borderBottom: selected ? "2px solid #60a5fa" : "1px solid var(--border-color)",
        borderLeft: "4px solid #60a5fa",
        borderRadius: 8,
        padding: "10px 14px",
        minWidth: 200,
        maxWidth: 300,
        opacity: d.is_active === false ? 0.4 : 1,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "#60a5fa" }} />
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{d.label}</div>
      <div style={{ fontSize: 10, color: "#60a5fa", fontFamily: "monospace" }}>{d.node_key}</div>
      {d.formula && (
        <div
          style={{
            fontSize: 10,
            fontFamily: "monospace",
            color: "var(--text-secondary)",
            marginTop: 4,
            padding: "3px 6px",
            background: "rgba(96, 165, 250, 0.08)",
            borderRadius: 4,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {d.formula}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: "#60a5fa" }} />
    </div>
  );
}
