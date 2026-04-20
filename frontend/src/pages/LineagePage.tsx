import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";

interface LineageNode { node_key: string; node_name: string; node_type: string; stream: string; execution_order: number | null; formula: string | null; formula_resolved: string | null; result: string | null; prior_value: string | null; delta_pct: string | null; is_suspect: boolean; suspect_reason: string | null; upstream_keys: string[]; comparison_value: string | null; difference: string | null; tolerance: string | null; validation_passed: boolean | null; input_source: string | null; cell_ref: string | null; }
interface LineageResponse { target_node_key: string; target_node_name: string; target_node_type: string; target_result: string | null; lineage_count: number; nodes: LineageNode[]; }

const fmt = (v: string | null) => { if (!v) return "—"; const n = parseFloat(v); return isNaN(n) ? v : `$${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`; };
const typeColor: Record<string, string> = { input_value: "#4ade80", input: "#4ade80", calculation: "#60a5fa", distribution: "#a78bfa", validation: "#fbbf24" };

export function LineagePage() {
  const { dealId, runId, nodeKey } = useParams<{ dealId: string; runId: string; nodeKey: string }>();
  const navigate = useNavigate();
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!dealId || !runId || !nodeKey) return;
    setLoading(true);
    api.get<LineageResponse>(`/deals/${dealId}/runs/${runId}/lineage/${nodeKey}`)
      .then(setLineage).catch(() => {}).finally(() => setLoading(false));
  }, [dealId, runId, nodeKey]);

  const isValidationFail = lineage?.nodes?.[0]?.node_type === "validation" && lineage?.nodes?.[0]?.validation_passed === false;
  const suspects = lineage?.nodes.filter((n) => n.is_suspect) ?? [];

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
        <Link to={`/deals/${dealId}`} style={{ color: "var(--accent-blue)", textDecoration: "none" }}>Deal</Link>
        {" / "}<Link to={`/deals/${dealId}/runs/${runId}/trace`} style={{ color: "var(--accent-blue)", textDecoration: "none" }}>Execution trace</Link>
        {" / "}{isValidationFail ? "Failure investigation" : "Calculation lineage"}
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">{isValidationFail ? `Investigate: ${lineage?.target_node_name}` : `Tracing: ${lineage?.target_node_name}`}</div>
          <div className="page-subtitle">{lineage?.target_node_type} node · {lineage?.lineage_count ?? 0} nodes in lineage</div>
        </div>
        <button className="btn btn-secondary" onClick={() => navigate(`/deals/${dealId}/runs/${runId}/trace`)}>Full trace</button>
      </div>

      {loading && <div style={{ color: "var(--text-muted)" }}>Loading lineage...</div>}

      {/* Target card */}
      {lineage && (
        <div className="card" style={{ marginBottom: 20, ...(isValidationFail ? { background: "rgba(248,113,113,0.05)", borderColor: "rgba(248,113,113,0.3)" } : {}) }}>
          {isValidationFail && lineage.nodes[0] && <>
            <div style={{ fontWeight: 600, color: "var(--accent-red)", marginBottom: 4 }}>Validation node: {lineage.target_node_name}</div>
            <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 12 }}>
              Our calculated value does not match the servicer tape. Difference of {fmt(lineage.nodes[0].difference)} exceeds ±{lineage.nodes[0].tolerance ?? "0.01"} tolerance.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              <div><div style={{ fontSize: 11, color: "var(--text-muted)" }}>Our calculation</div><div style={{ fontSize: 16, fontWeight: 600 }}>{fmt(lineage.nodes[0].result)}</div></div>
              <div><div style={{ fontSize: 11, color: "var(--text-muted)" }}>Tape value</div><div style={{ fontSize: 16, fontWeight: 600 }}>{fmt(lineage.nodes[0].comparison_value)}</div></div>
              <div><div style={{ fontSize: 11, color: "var(--text-muted)" }}>Difference</div><div style={{ fontSize: 16, fontWeight: 600, color: "var(--accent-red)" }}>{fmt(lineage.nodes[0].difference)}</div></div>
              <div><div style={{ fontSize: 11, color: "var(--text-muted)" }}>Tolerance</div><div style={{ fontSize: 16, fontWeight: 600 }}>±{lineage.nodes[0].tolerance ?? "0.01"}</div></div>
            </div>
          </>}
          {!isValidationFail && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: typeColor[lineage.target_node_type] ?? "#999", marginRight: 6, verticalAlign: "middle" }} /><span style={{ fontWeight: 600 }}>{lineage.target_node_name}</span></div>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{fmt(lineage.target_result)}</div>
            </div>
          )}
        </div>
      )}

      {/* Lineage tree */}
      {lineage && <div style={{ fontSize: 14, fontWeight: 500, margin: "20px 0 12px" }}>Calculation lineage — every node that feeds into {isValidationFail ? "the check" : "this value"} <span style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 400 }}>{lineage.lineage_count} nodes</span></div>}

      {lineage?.nodes.map((node, idx) => (
        <div key={node.node_key} style={{
          border: `1px solid ${node.is_suspect ? "rgba(248,113,113,0.5)" : node.validation_passed === false ? "rgba(248,113,113,0.5)" : "var(--border)"}`,
          borderRadius: 6, padding: "12px 16px", marginBottom: 8, marginLeft: idx === 0 ? 0 : 24,
          background: node.is_suspect ? "rgba(248,113,113,0.03)" : node.validation_passed === false ? "rgba(248,113,113,0.05)" : "var(--bg-secondary)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {idx > 0 && <span style={{ color: "var(--text-muted)", fontSize: 12 }}>←</span>}
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: typeColor[node.node_type] ?? "#999" }} />
            <span style={{ fontWeight: 500 }}>{node.node_name}</span>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{node.node_type} · Step {node.execution_order}</span>
            {node.is_suspect && <span style={{ fontSize: 10, background: "rgba(248,113,113,0.15)", color: "var(--accent-red)", padding: "2px 8px", borderRadius: 4, fontWeight: 500 }}>Likely culprit</span>}
            {!node.is_suspect && node.result && idx > 0 && <span style={{ fontSize: 10, background: "rgba(74,222,128,0.1)", color: "var(--accent-green)", padding: "2px 8px", borderRadius: 4 }}>OK</span>}
            <span style={{ flex: 1 }} />
            <span style={{ fontWeight: 600 }}>{fmt(node.result)}</span>
          </div>
          {node.formula && (
            <div style={{ marginTop: 8, padding: 8, background: "var(--bg-tertiary)", borderRadius: 4 }}>
              <div style={{ fontFamily: "monospace", fontSize: 12 }}>{node.formula}</div>
              {node.formula_resolved && <div style={{ fontFamily: "monospace", fontSize: 11, color: "var(--accent-green)", marginTop: 2 }}>{node.formula_resolved}</div>}
            </div>
          )}
          {node.prior_value && (
            <div style={{ fontSize: 11, color: "var(--accent-orange)", background: "rgba(251,191,36,0.05)", border: "1px solid rgba(251,191,36,0.2)", borderRadius: 4, padding: "6px 10px", marginTop: 8 }}>
              Prior month value was {fmt(node.prior_value)}
              {node.delta_pct && <span> — a change of {(parseFloat(node.delta_pct) * 100).toFixed(1)}%</span>}
            </div>
          )}
          {node.is_suspect && node.suspect_reason && <div style={{ fontSize: 12, color: "var(--accent-red)", marginTop: 6 }}>{node.suspect_reason}</div>}
        </div>
      ))}

      {/* Probable causes */}
      {isValidationFail && suspects.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>Probable causes</h3>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>Ranked by likelihood based on the discrepancy pattern</div>
          {suspects.map((s, i) => (
            <div key={s.node_key} style={{ display: "flex", gap: 12, padding: "10px 0", borderBottom: i < suspects.length - 1 ? "1px solid var(--border)" : "none" }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: "var(--accent-red)", minWidth: 24 }}>#{i + 1}</span>
              <div><div style={{ fontWeight: 500, fontSize: 13 }}>{s.node_name}</div><div style={{ fontSize: 12, color: "var(--text-muted)" }}>{s.suspect_reason}</div></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
