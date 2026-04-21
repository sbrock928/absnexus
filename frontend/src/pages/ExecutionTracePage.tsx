import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";

interface RunData { id: number; deal_id: number; report_period: string; status: string; total_distribution: string | null; validations_passed: number | null; validations_total: number | null; created_by: string; }
interface Step { order: number; key: string; name: string; type: string; stream: string; formula: string | null; resolved: string | null; result: string | null; export_field: string | null; payment_type: string | null; comparison_value: string | null; comparison_variable?: string | null; comparison_data_type?: string | null; tolerance: string | null; tolerance_type: string | null; difference: string | null; passed: number | null; }

const fmt = (v: string | null) => { if (!v) return "—"; const n = parseFloat(v); return isNaN(n) ? v : `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; };
const fmtByType = (v: string | null, dtype?: string | null): string => {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (isNaN(n)) return v;
  if (dtype === "integer") return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (dtype === "percentage") return `${(n * 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}%`;
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
const dotColor: Record<string, string> = { input_value: "#4ade80", calculation: "#60a5fa", distribution: "#a78bfa", validation: "#fbbf24" };

export function ExecutionTracePage() {
  const { dealId, runId } = useParams<{ dealId: string; runId: string }>();
  const navigate = useNavigate();
  const [run, setRun] = useState<RunData | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);

  useEffect(() => {
    if (!dealId || !runId) return;
    api.get<RunData>(`/deals/${dealId}/runs/${runId}`).then(setRun);
    api.get<Step[]>(`/deals/${dealId}/runs/${runId}/trace`).then(setSteps);
  }, [dealId, runId]);

  const inputs = steps.filter((s) => s.type === "input_value");
  const calcs = steps.filter((s) => s.type === "calculation");
  const dists = steps.filter((s) => s.type === "distribution");
  const vals = steps.filter((s) => s.type === "validation");
  const allPassed = vals.every((v) => v.passed === 1);
  const passCount = vals.filter((v) => v.passed === 1).length;

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
        <Link to={`/deals/${dealId}`} style={{ color: "var(--accent-blue)", textDecoration: "none" }}>Deal</Link> / Processing / Execution trace
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Execution trace — RUN-{runId}</div>
          <div className="page-subtitle">{run?.report_period ?? "..."}</div>
        </div>
        <Link to={`/deals/${dealId}`} className="btn btn-secondary" style={{ textDecoration: "none" }}>Back to deal</Link>
      </div>

      {/* Banner */}
      <div style={{ padding: "12px 16px", borderRadius: 6, fontSize: 13, marginBottom: 16, background: allPassed ? "rgba(74,222,128,0.1)" : "rgba(248,113,113,0.1)", border: `1px solid ${allPassed ? "rgba(74,222,128,0.3)" : "rgba(248,113,113,0.3)"}`, color: allPassed ? "var(--accent-green)" : "var(--accent-red)" }}>
        {allPassed ? `All ${steps.length} nodes executed successfully · ${passCount} validations passed` : `Execution complete with ${vals.length - passCount} validation failure(s)`}
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <div className="card"><div style={{ fontSize: 11, color: "var(--text-muted)" }}>Input variables</div><div style={{ fontSize: 18, fontWeight: 600 }}>{inputs.length}</div></div>
        <div className="card"><div style={{ fontSize: 11, color: "var(--text-muted)" }}>Calculations</div><div style={{ fontSize: 18, fontWeight: 600 }}>{calcs.length}</div></div>
        <div className="card"><div style={{ fontSize: 11, color: "var(--text-muted)" }}>Distribution outputs</div><div style={{ fontSize: 18, fontWeight: 600 }}>{dists.length}</div></div>
        <div className="card"><div style={{ fontSize: 11, color: "var(--text-muted)" }}>Validations</div><div style={{ fontSize: 18, fontWeight: 600, color: allPassed ? "var(--accent-green)" : "var(--accent-red)" }}>{passCount}/{vals.length}</div></div>
      </div>

      {/* Section 1: Inputs */}
      <h3 style={{ fontSize: 14, fontWeight: 500, margin: "24px 0 8px" }}>Input variables (extracted from tape)</h3>
      <table className="table"><thead><tr><th>#</th><th>Node</th><th>Source</th><th style={{ textAlign: "right" }}>Extracted value</th></tr></thead>
        <tbody>{inputs.map((s) => (<tr key={s.order}><td style={{ color: "var(--text-muted)" }}>{s.order}</td><td><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: dotColor[s.type], marginRight: 6, verticalAlign: "middle" }} />{s.name}</td><td style={{ color: "var(--text-muted)", fontSize: 12 }}>{s.key}</td><td style={{ textAlign: "right", color: "var(--accent-green)", fontFamily: "monospace" }}>{fmt(s.result)}</td></tr>))}</tbody></table>

      {/* Section 2: Intermediate calculations */}
      <h3 style={{ fontSize: 14, fontWeight: 500, margin: "24px 0 8px" }}>Intermediate calculations</h3>
      <table className="table"><thead><tr><th>#</th><th>Node</th><th>Formula → resolved</th><th style={{ textAlign: "right" }}>Result</th></tr></thead>
        <tbody>{calcs.map((s) => (<tr key={s.order}><td style={{ color: "var(--text-muted)" }}>{s.order}</td><td><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: dotColor[s.type], marginRight: 6, verticalAlign: "middle" }} />{s.name}</td><td><code style={{ fontSize: 12 }}>{s.formula}</code>{s.resolved && <div style={{ fontSize: 11, color: "var(--accent-green)", fontFamily: "monospace" }}>{s.resolved}</div>}</td><td style={{ textAlign: "right", fontWeight: 500 }}>{fmt(s.result)}</td></tr>))}</tbody></table>

      {/* Section 3: Distribution outputs */}
      <h3 style={{ fontSize: 14, fontWeight: 500, margin: "24px 0 8px" }}>Distribution outputs (exported to payment template)</h3>
      <table className="table"><thead><tr><th>#</th><th>Node</th><th>Formula → resolved</th><th>Export field</th><th style={{ textAlign: "right" }}>Payment</th></tr></thead>
        <tbody>{dists.map((s) => (<tr key={s.order}><td style={{ color: "var(--text-muted)" }}>{s.order}</td><td><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: dotColor[s.type], marginRight: 6, verticalAlign: "middle" }} />{s.name}</td><td><code style={{ fontSize: 12 }}>{s.formula}</code>{s.resolved && <div style={{ fontSize: 11, color: "var(--accent-green)", fontFamily: "monospace" }}>{s.resolved}</div>}</td><td>{s.export_field ? <code style={{ fontSize: 11, color: "var(--accent-green)", background: "rgba(74,222,128,0.1)", padding: "2px 8px", borderRadius: 4, border: "1px solid rgba(74,222,128,0.3)" }}>{s.export_field}</code> : "—"}</td><td style={{ textAlign: "right", fontWeight: 600 }}>{fmt(s.result)}</td></tr>))}</tbody></table>

      {/* Section 4: Validation checks */}
      {vals.length > 0 && <>
        <h3 style={{ fontSize: 14, fontWeight: 500, margin: "24px 0 8px" }}>Validation checks</h3>
        <table className="table"><thead><tr><th>#</th><th>Node</th><th>Calculated</th><th>Tape</th><th>Difference</th><th>Result</th><th></th></tr></thead>
          <tbody>{vals.map((s) => (<tr key={s.order} style={s.passed === 0 ? { background: "rgba(248,113,113,0.05)" } : {}}>
            <td style={{ color: "var(--text-muted)" }}>{s.order}</td>
            <td><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: dotColor[s.type], marginRight: 6, verticalAlign: "middle" }} />{s.name}</td>
            <td style={{ fontFamily: "monospace" }}>{fmtByType(s.result, s.comparison_data_type)}</td>
            <td style={{ fontFamily: "monospace" }}>{fmtByType(s.comparison_value, s.comparison_data_type)}</td>
            <td style={{ fontFamily: "monospace", color: s.passed === 0 ? "var(--accent-red)" : "var(--text-muted)" }}>{fmtByType(s.difference, s.comparison_data_type)}</td>
            <td>{s.passed === 1 ? <span className="badge badge-active">Pass</span> : <span style={{ color: "var(--accent-red)", fontWeight: 600 }}>Fail</span>}</td>
            <td><button onClick={() => navigate(`/deals/${dealId}/runs/${runId}/lineage/${s.key}`)} style={{ fontSize: 12, color: "var(--accent-blue)", background: "none", border: "none", cursor: "pointer" }}>{s.passed === 0 ? "Investigate" : "Trace"}</button></td>
          </tr>))}</tbody></table>
      </>}
    </div>
  );
}
