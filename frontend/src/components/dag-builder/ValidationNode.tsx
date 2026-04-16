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
        padding: "8px 12px",
        minWidth: 160,
        opacity: d.is_active === false ? 0.4 : 1,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "#fbbf24" }} />
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{d.label}</div>
      <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
        Validation · ±{d.tolerance ?? "0.01"}
      </div>
      {d.formula && (
        <div
          style={{
            fontSize: 10,
            fontFamily: "var(--font-mono)",
            color: "var(--text-secondary)",
            marginTop: 4,
            maxWidth: 200,
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
