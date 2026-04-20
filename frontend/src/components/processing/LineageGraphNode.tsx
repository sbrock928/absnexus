import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface LineageNodeData {
  name: string;
  node_key: string;
  node_type: string;
  value: string | null;
  formula: string | null;
  is_target?: boolean;
  [key: string]: unknown;
}

const COLORS: Record<string, string> = {
  input_value: "#4ade80",
  input: "#4ade80",
  calculation: "#60a5fa",
  distribution: "#a78bfa",
  validation: "#fbbf24",
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

export function LineageGraphNode({ data }: NodeProps) {
  const d = data as LineageNodeData;
  const accent = COLORS[d.node_type] ?? "#9ca3af";
  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: d.is_target
          ? `2px solid ${accent}`
          : "1px solid var(--border-color)",
        borderLeft: `4px solid ${accent}`,
        borderRadius: 8,
        padding: "10px 14px",
        minWidth: 220,
        maxWidth: 320,
        boxShadow: d.is_target ? `0 0 0 3px ${accent}33` : undefined,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: accent }} />
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 2 }}>{d.name}</div>
      <div style={{ fontSize: 10, color: accent, fontFamily: "monospace", marginBottom: 6 }}>
        {d.node_key}
      </div>
      <div
        style={{
          fontSize: 14,
          fontWeight: 600,
          fontFamily: "var(--font-mono)",
          color: "var(--text-primary)",
        }}
      >
        {fmt(d.value)}
      </div>
      {d.formula && (
        <div
          style={{
            fontSize: 10,
            fontFamily: "monospace",
            color: "var(--text-secondary)",
            marginTop: 6,
            padding: "3px 6px",
            background: "rgba(255,255,255,0.04)",
            borderRadius: 4,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={d.formula}
        >
          {d.formula}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: accent }} />
    </div>
  );
}
