import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { DagNodeData } from "./types";

export function InputNode({ data, selected }: NodeProps) {
  const d = data as DagNodeData;
  return (
    <div
      style={{
        background: "var(--bg-card)",
        borderTop: selected ? "2px solid #4ade80" : "1px solid var(--border-color)",
        borderRight: selected ? "2px solid #4ade80" : "1px solid var(--border-color)",
        borderBottom: selected ? "2px solid #4ade80" : "1px solid var(--border-color)",
        borderLeft: "4px solid #4ade80",
        borderRadius: 8,
        padding: "10px 14px",
        minWidth: 200,
        maxWidth: 280,
        opacity: d.is_active === false ? 0.4 : 1,
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{d.label}</div>
      <div style={{ fontSize: 10, color: "#4ade80", fontFamily: "monospace" }}>{d.node_key}</div>
      <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>
        Input · {d.input_source === "tranche" ? "Tranche" : "Tape"}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: "#4ade80" }} />
    </div>
  );
}
