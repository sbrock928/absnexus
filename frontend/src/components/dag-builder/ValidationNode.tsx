import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { DagNodeData } from "./types";

export function ValidationNode({ data, selected }: NodeProps) {
  const d = data as DagNodeData;
  return (
    <div
      style={{
        background: "var(--bg-card)",
        borderTop: selected ? "2px solid #fbbf24" : "1px solid var(--border-color)",
        borderRight: selected ? "2px solid #fbbf24" : "1px solid var(--border-color)",
        borderBottom: selected ? "2px solid #fbbf24" : "1px solid var(--border-color)",
        borderLeft: "4px solid #fbbf24",
        borderRadius: 8,
        padding: "10px 14px",
        minWidth: 200,
        maxWidth: 300,
        opacity: d.is_active === false ? 0.4 : 1,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "#fbbf24" }} />
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{d.label}</div>
      <div style={{ fontSize: 10, color: "#fbbf24", fontFamily: "monospace" }}>{d.node_key}</div>
      <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2 }}>
        Validation · ±{d.tolerance ?? "0.01"}
        {d.comparison_var && (
          <span style={{ marginLeft: 4 }}>vs <span style={{ color: "var(--accent-green)", fontFamily: "monospace" }}>{d.comparison_var}</span></span>
        )}
      </div>
      {d.formula && (
        <div
          style={{
            fontSize: 10,
            fontFamily: "monospace",
            color: "var(--text-secondary)",
            marginTop: 4,
            padding: "3px 6px",
            background: "rgba(251, 191, 36, 0.08)",
            borderRadius: 4,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {d.formula}
        </div>
      )}
    </div>
  );
}
