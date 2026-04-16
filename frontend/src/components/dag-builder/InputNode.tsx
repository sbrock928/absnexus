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
        padding: "8px 12px",
        minWidth: 160,
        opacity: d.is_active === false ? 0.4 : 1,
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{d.label}</div>
      <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
        Input · {d.input_source === "tranche" ? "Tranche" : "Tape"}
      </div>
      {d.cell_ref && (
        <div
          style={{
            fontSize: 10,
            fontFamily: "var(--font-mono)",
            color: "var(--accent-blue)",
            marginTop: 2,
          }}
        >
          {d.cell_ref}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: "#4ade80" }} />
    </div>
  );
}
