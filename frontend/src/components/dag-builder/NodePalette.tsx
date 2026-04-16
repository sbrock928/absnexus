const NODE_TYPES = [
  { type: "input_value", label: "Input variable", color: "#4ade80" },
  { type: "calculation", label: "Calculation", color: "#60a5fa" },
  { type: "distribution", label: "Distribution", color: "#a78bfa" },
  { type: "validation", label: "Validation", color: "#fbbf24" },
];

export function NodePalette({ onAddNode }: { onAddNode: (type: string) => void }) {
  return (
    <div style={{ width: 160, background: "var(--bg-secondary)", borderRight: "1px solid var(--border)", padding: 12, flexShrink: 0 }}>
      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: 8 }}>Node types</div>
      {NODE_TYPES.map((nt) => (
        <button key={nt.type} onClick={() => onAddNode(nt.type)} style={{
          display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "6px 8px", marginBottom: 4,
          border: "1px solid var(--border)", borderRadius: 6, background: "var(--bg-tertiary)",
          color: "var(--text-primary)", fontSize: 12, cursor: "pointer",
        }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: nt.color, flexShrink: 0 }} />
          {nt.label}
        </button>
      ))}
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 12 }}>
        Click to add a node. Drag nodes on the canvas to reposition.
      </div>
    </div>
  );
}
