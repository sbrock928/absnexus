import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { DagNodeData } from "./types";

export function DistNode({ data, selected }: NodeProps) {
  const d = data as DagNodeData;
  return (
    <div
      style={{
        background: "var(--bg-card)",
        borderTop: selected ? "2px solid #a78bfa" : "1px solid var(--border-color)",
        borderRight: selected ? "2px solid #a78bfa" : "1px solid var(--border-color)",
        borderBottom: selected ? "2px solid #a78bfa" : "1px solid var(--border-color)",
        borderLeft: "4px solid #a78bfa",
        borderRadius: 8,
        padding: "10px 14px",
        minWidth: 200,
        maxWidth: 300,
        opacity: d.is_active === false ? 0.4 : 1,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: "#a78bfa" }} />
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{d.label}</div>
      <div style={{ fontSize: 10, color: "#a78bfa", fontFamily: "monospace" }}>{d.node_key}</div>
      <div style={{ fontSize: 9, color: "var(--text-muted)", marginTop: 2, display: "flex", gap: 4, alignItems: "center" }}>
        Distribution
        {d.export_field && (
          <span style={{ fontSize: 9, fontFamily: "monospace", background: "rgba(74, 222, 128, 0.15)", color: "var(--accent-green)", padding: "1px 5px", borderRadius: 3 }}>
            {d.export_field}
          </span>
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
            background: "rgba(167, 139, 250, 0.08)",
            borderRadius: 4,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {d.formula}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: "#a78bfa" }} />
    </div>
  );
}
