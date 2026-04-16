import { useEffect, useState, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api/client";
import { listTemplates, type GlobalTemplate } from "../api/globalExport";
import { WaterfallTrace } from "../components/processing/WaterfallTrace";
import { CellMapperModal } from "../components/cell-mapper/CellMapperModal";
import { reextractVariable } from "../api/mappings";
import type { Deal, Servicer } from "../types";

interface ExtractedVar { variable_id?: number; variable: string; cell: string; sheet: string; raw: string | null; parsed: string | null; prior: string | null; pct_change: string | null; warning: string | null; }
interface ExecStep { order: number; key: string; name: string; type: string; stream: string; formula: string | null; resolved: string | null; result: string | null; export_field: string | null; passed: number | null; difference: string | null; comparison_value?: string | null; tolerance?: string | null; tolerance_type?: string | null; payment_type?: string | null; }

const STEPS = ["Select deal", "Upload tape", "Extract", "Execute", "Waterfall", "Export"];
const nodeColor: Record<string, string> = { input_value: "var(--accent-green)", calculation: "var(--accent-blue)", distribution: "var(--accent-purple)", validation: "var(--accent-orange)" };
const fmtMoney = (v: string | null) => v ? `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—";

/* Map run.status → highest completed step index */
function statusToStep(status: string): number {
  switch (status) {
    case "pending": return 1;      // tape uploaded but nothing else
    case "extracting": return 2;
    case "extracted": return 3;    // extraction done → show results
    case "executing": return 3;
    case "executed": return 4;     // execution done → show results
    case "failed": return 4;       // execution failed → still show step 4
    case "completed": return 6;    // export done
    default: return 1;
  }
}

export function ProcessingPage() {
  const { isModeler } = useAuth();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [servicers, setServicers] = useState<Servicer[]>([]);
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null);
  const [period, setPeriod] = useState(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; });
  const [step, setStep] = useState(0);
  const [run, setRun] = useState<any>(null);
  const [vars, setVars] = useState<ExtractedVar[]>([]);
  const [steps, setSteps] = useState<ExecStep[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [exportRes, setExportRes] = useState<any>(null);
  const [exportTemplates, setExportTemplates] = useState<GlobalTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [existingRuns, setExistingRuns] = useState<any[]>([]);
  const [remappingVariable, setRemappingVariable] = useState<{
    variable_id: number;
    variable_name: string;
  } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  /* Track the furthest step completed so we know which steps are clickable */
  const [maxStep, setMaxStep] = useState(0);

  useEffect(() => {
    Promise.all([api.get<Deal[]>("/deals/"), api.get<Servicer[]>("/servicers/")]).then(([d, s]) => { setDeals(d); setServicers(s); });
    listTemplates().then((t) => { setExportTemplates(t); if (t.length > 0) setSelectedTemplateId(t[0].id); });
  }, []);

  const svcName = (id: number) => servicers.find((s) => s.id === id)?.name ?? "";

  const reset = () => { setStep(0); setRun(null); setVars([]); setSteps([]); setSummary(null); setExportRes(null); setError(""); setSelectedDeal(null); setMaxStep(0); setExistingRuns([]); };

  /* ── Load read-only data for a given step without reprocessing ── */
  const loadExtracted = useCallback(async (dealId: number, runId: number) => {
    const data = await api.get<any>(`/deals/${dealId}/runs/${runId}/extracted`);
    setVars(data.values || []);
  }, []);

  const loadTrace = useCallback(async (dealId: number, runId: number) => {
    const data = await api.get<ExecStep[]>(`/deals/${dealId}/runs/${runId}/trace`);
    setSteps(data);
  }, []);

  /* Navigate to a step, loading cached data as needed (no reprocessing) */
  const goToStep = useCallback(async (target: number) => {
    if (!selectedDeal || !run) { setStep(target); return; }
    setError("");
    try {
      if (target === 3 && vars.length === 0) await loadExtracted(selectedDeal.id, run.id);
      if (target === 4 && steps.length === 0) {
        await loadTrace(selectedDeal.id, run.id);
        // rebuild summary from run object
        setSummary({
          total_distribution: run.total_distribution,
          validations_passed: run.validations_passed,
          validations_total: run.validations_total,
          errors: run.error_message ? [run.error_message] : [],
          steps: [],
        });
      }
    } catch (e: any) { setError(e.message); }
    setStep(target);
  }, [selectedDeal, run, vars, steps, loadExtracted, loadTrace]);

  /* ── When a deal is selected, check for existing runs for this period ── */
  const handleSelectDeal = async (deal: Deal) => {
    setSelectedDeal(deal);
    setError("");
    try {
      const runs = await api.get<any[]>(`/deals/${deal.id}/runs`);
      const periodRuns = runs.filter((r: any) => r.report_period === period);
      setExistingRuns(periodRuns);
      if (periodRuns.length > 0) {
        // Stay on step 0 but show run picker — or if only one, auto-resume
        setStep(1);
      } else {
        setStep(1);
      }
    } catch {
      setStep(1);
    }
  };

  /* Resume an existing run — jump to the furthest completed step */
  const handleResumeRun = async (existingRun: any) => {
    setRun(existingRun);
    setExistingRuns([]);
    const resumeStep = statusToStep(existingRun.status);
    setMaxStep(resumeStep);

    // Pre-load data for the step we're jumping to
    try {
      if (resumeStep >= 3) await loadExtracted(selectedDeal!.id, existingRun.id);
      if (resumeStep >= 4) {
        await loadTrace(selectedDeal!.id, existingRun.id);
        setSummary({
          total_distribution: existingRun.total_distribution,
          validations_passed: existingRun.validations_passed,
          validations_total: existingRun.validations_total,
          errors: existingRun.error_message ? [existingRun.error_message] : [],
          steps: [],
        });
      }
      if (resumeStep >= 6 && existingRun.export_file_path) {
        setExportRes({ file_path: existingRun.export_file_path, hash: existingRun.export_file_hash });
      }
    } catch (e: any) { setError(e.message); }

    setStep(resumeStep);
  };

  const handleUpload = async () => {
    if (!selectedDeal || !fileRef.current?.files?.length) return;
    setLoading(true); setError("");
    try {
      const newRun = await api.post<any>(`/deals/${selectedDeal.id}/runs`, { report_period: period });
      setRun(newRun);
      const fd = new FormData(); fd.append("file", fileRef.current.files[0]);
      const res = await fetch(`/api/deals/${selectedDeal.id}/runs/${newRun.id}/upload`, { method: "POST", body: fd });
      if (!res.ok) throw new Error("Upload failed");
      setMaxStep(2);
      setStep(2);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  };

  const handleExtract = async () => {
    if (!selectedDeal || !run) return;
    setLoading(true); setError("");
    try {
      const data = await api.post<any>(`/deals/${selectedDeal.id}/runs/${run.id}/extract`);
      setVars(data.values);
      setMaxStep((m) => Math.max(m, 3));
      setStep(3);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  };

  const handleExecute = async () => {
    if (!selectedDeal || !run) return;
    setLoading(true); setError("");
    try {
      const data = await api.post<any>(`/deals/${selectedDeal.id}/runs/${run.id}/execute`);
      setSummary(data); setSteps(data.steps || []);
      // Refresh run object with latest fields
      const freshRun = await api.get<any>(`/deals/${selectedDeal.id}/runs/${run.id}`);
      setRun(freshRun);
      setMaxStep((m) => Math.max(m, 4));
      setStep(4);
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  };

  const handleExport = async () => {
    if (!selectedDeal || !run || !selectedTemplateId) return;
    setLoading(true); setError("");
    try {
      const data = await api.post<any>(`/deals/${selectedDeal.id}/runs/${run.id}/export?template_id=${selectedTemplateId}`);
      setExportRes(data);
      setMaxStep((m) => Math.max(m, 6));
    } catch (e: any) { setError(e.message); } finally { setLoading(false); }
  };

  /* Which steps can be clicked to navigate back */
  const canNavigate = (i: number): boolean => {
    if (i > maxStep) return false;
    // Steps 0 (deal select) and 1 (upload) are only navigable via "Start over"
    if (i <= 1) return false;
    return true;
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Monthly Processing{selectedDeal ? ` — ${period}` : ""}</div>
          <div className="page-subtitle">{selectedDeal ? `${selectedDeal.name} · ${svcName(selectedDeal.servicer_id)}` : "Select a deal to begin"}</div>
        </div>
        {step > 0 && <button className="btn btn-secondary" onClick={reset}>Start over</button>}
      </div>

      {/* Stepper — clickable for completed steps */}
      <div style={{ display: "flex", gap: 0, marginBottom: 24 }}>
        {STEPS.map((s, i) => {
          const completed = i < maxStep;
          const active = i === step;
          const clickable = canNavigate(i) && i !== step;
          return (
            <div
              key={s}
              style={{ flex: 1, display: "flex", alignItems: "center", cursor: clickable ? "pointer" : "default" }}
              onClick={() => clickable && goToStep(i)}
            >
              <div style={{
                width: 28, height: 28, borderRadius: "50%",
                background: active ? "var(--accent-blue)" : completed ? "var(--accent-green)" : "var(--bg-tertiary)",
                color: active || completed ? "#000" : "var(--text-muted)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 12, fontWeight: 600, flexShrink: 0,
                transition: "all 0.15s",
                outline: clickable ? "2px solid transparent" : "none",
              }}
              onMouseEnter={(e) => { if (clickable) e.currentTarget.style.outline = "2px solid var(--accent-blue)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.outline = "2px solid transparent"; }}
              >
                {completed && i !== step ? "✓" : i + 1}
              </div>
              <div style={{ fontSize: 12, marginLeft: 6, color: active ? "var(--text-primary)" : completed ? "var(--accent-green)" : "var(--text-muted)", fontWeight: active ? 600 : 400 }}>{s}</div>
              {i < STEPS.length - 1 && <div style={{ flex: 1, height: 1, background: completed ? "var(--accent-green)" : "var(--border)", margin: "0 8px" }} />}
            </div>
          );
        })}
      </div>

      {error && <div className="banner banner-warn" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Step 0: Deal selection */}
      {step === 0 && (
        <div>
          <div style={{ marginBottom: 16 }}>
            <label className="form-label">Report period (YYYY-MM)</label>
            <input className="input" value={period} onChange={(e) => setPeriod(e.target.value)} placeholder="2026-04" style={{ width: 200 }} />
            {period && !/^\d{4}-\d{2}$/.test(period) && <div style={{ color: "var(--accent-yellow)", fontSize: 12, marginTop: 4 }}>Format must be YYYY-MM (e.g. 2026-04)</div>}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
            {deals.filter(d => isModeler ? true : d.status === "active").map((d) => (
              <div key={d.id} className="card" style={{ cursor: "pointer" }} onClick={() => handleSelectDeal(d)}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--accent-blue)")}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {d.name}
                  {isModeler && d.status !== "active" && (
                    <span className={`badge badge-${d.status}`} style={{ marginLeft: 8 }}>{d.status}</span>
                  )}
                </div>
                <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{svcName(d.servicer_id)} · {d.product_type}</div>
              </div>
            ))}
          </div>
          {deals.filter(d => isModeler ? true : d.status === "active").length === 0 && <div className="empty-state"><div className="empty-state-title">No active deals</div></div>}
        </div>
      )}

      {/* Step 1: Upload — or resume an existing run */}
      {step === 1 && (
        <div>
          {existingRuns.length > 0 && (
            <div className="card" style={{ marginBottom: 16, borderColor: "var(--accent-blue)" }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>Existing runs for {period}</div>
              <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 12 }}>Resume a previous run to view results without reprocessing, or upload a new tape below.</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {existingRuns.map((r: any) => (
                  <div key={r.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", background: "var(--bg-secondary)", borderRadius: 6, border: "1px solid var(--border)" }}>
                    <div>
                      <span style={{ fontWeight: 600 }}>RUN-{r.id}</span>
                      <span className={`badge badge-${r.status === "completed" ? "active" : r.status === "failed" ? "deal" : "default"}`} style={{ marginLeft: 8, fontSize: 10 }}>{r.status}</span>
                      {r.total_distribution != null && <span style={{ marginLeft: 12, color: "var(--text-muted)", fontSize: 12 }}>dist: {fmtMoney(String(r.total_distribution))}</span>}
                      {r.validations_passed != null && <span style={{ marginLeft: 8, color: r.validations_passed === r.validations_total ? "var(--accent-green)" : "var(--accent-orange)", fontSize: 12 }}>{r.validations_passed}/{r.validations_total} validations</span>}
                    </div>
                    <button className="btn btn-primary btn-sm" onClick={() => handleResumeRun(r)}>Resume</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card" style={{ maxWidth: 500 }}>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>{existingRuns.length > 0 ? "Or upload a new tape" : "Upload servicer tape"}</div>
            <div className="form-field"><label className="form-label">Excel file (.xlsx)</label><input ref={fileRef} type="file" accept=".xlsx,.xls" className="input" style={{ padding: 8 }} /></div>
            <div className="btn-group">
              <button className="btn btn-secondary" onClick={() => { setExistingRuns([]); setStep(0); }}>Back</button>
              <button className="btn btn-primary" onClick={handleUpload} disabled={loading}>{loading ? "Uploading..." : "Upload & create run"}</button>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Extract prompt */}
      {step === 2 && (
        <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div><div style={{ fontWeight: 600 }}>Tape uploaded successfully</div><div style={{ fontSize: 13, color: "var(--text-muted)" }}>Ready to extract variables from mapped cells</div></div>
          <button className="btn btn-primary" onClick={handleExtract} disabled={loading}>{loading ? "Extracting..." : "Extract variables"}</button>
        </div>
      )}

      {/* Step 3: Extraction results + execute button */}
      {step === 3 && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div style={{ fontWeight: 600 }}>Variables extracted — {vars.length} mapped</div>
            <div className="btn-group">
              {maxStep >= 4 && <button className="btn btn-secondary btn-sm" onClick={() => goToStep(4)}>View execution →</button>}
              <button className="btn btn-primary" onClick={handleExecute} disabled={loading}>{loading ? "Executing..." : (maxStep >= 4 ? "Re-run calculations" : "Run calculations")}</button>
            </div>
          </div>
          {vars.some((v) => v.warning) && <div className="banner banner-warn" style={{ marginBottom: 12 }}>{vars.filter((v) => v.warning).length} warning(s)</div>}
          <table className="table">
            <thead><tr><th>#</th><th>Variable</th><th>Source</th><th>Extracted</th><th>Prior</th><th>Change</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {vars.map((v, i) => (
                <tr key={i} style={v.warning ? { background: "rgba(251,191,36,0.05)" } : {}}>
                  <td style={{ color: "var(--text-muted)" }}>{i + 1}</td>
                  <td><code style={{ color: "var(--accent-green)" }}>{v.variable}</code></td>
                  <td style={{ color: "var(--text-muted)", fontSize: 12 }}>{v.sheet} · {v.cell}</td>
                  <td style={{ fontFamily: "monospace" }}>{fmtMoney(v.parsed)}</td>
                  <td style={{ fontFamily: "monospace", color: "var(--text-muted)" }}>{fmtMoney(v.prior)}</td>
                  <td style={{ color: v.pct_change && Math.abs(Number(v.pct_change)) > 50 ? "var(--accent-yellow)" : "var(--text-muted)" }}>{v.pct_change ? `${Number(v.pct_change) > 0 ? "+" : ""}${v.pct_change}%` : "—"}</td>
                  <td>{v.warning ? <span style={{ color: "var(--accent-yellow)", fontSize: 12 }}>⚠ Warning</span> : <span style={{ color: "var(--accent-green)", fontSize: 12 }}>● OK</span>}</td>
                  <td>
                    {v.warning && (
                      <button
                        style={{ fontSize: 11, padding: "3px 10px", background: "rgba(96,165,250,0.1)", border: "1px solid rgba(96,165,250,0.3)", color: "var(--accent-blue)", borderRadius: 4, cursor: "pointer" }}
                        onClick={() => setRemappingVariable({ variable_id: (v as any).variable_id ?? 0, variable_name: v.variable })}
                      >
                        Remap
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Step 4: Execution results + waterfall button */}
      {step === 4 && (summary || steps.length > 0) && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
            <div className="card"><div style={{ color: "var(--text-muted)", fontSize: 12 }}>TOTAL DISTRIBUTION</div><div style={{ fontSize: 22, fontWeight: 600, color: "var(--accent-green)" }}>{fmtMoney(summary?.total_distribution ?? run?.total_distribution)}</div></div>
            <div className="card"><div style={{ color: "var(--text-muted)", fontSize: 12 }}>NODES EXECUTED</div><div style={{ fontSize: 22, fontWeight: 600 }}>{steps.length}</div></div>
            <div className="card"><div style={{ color: "var(--text-muted)", fontSize: 12 }}>VALIDATIONS</div><div style={{ fontSize: 22, fontWeight: 600, color: (summary?.validations_passed ?? run?.validations_passed) === (summary?.validations_total ?? run?.validations_total) ? "var(--accent-green)" : "var(--accent-red)" }}>{summary?.validations_passed ?? run?.validations_passed ?? "?"} / {summary?.validations_total ?? run?.validations_total ?? "?"} passed</div></div>
            <div className="card"><div style={{ color: "var(--text-muted)", fontSize: 12 }}>NEXT</div><button className="btn btn-primary btn-sm" onClick={() => { setMaxStep((m) => Math.max(m, 5)); setStep(5); }} style={{ marginTop: 4 }}>Waterfall check</button></div>
          </div>

          {summary?.errors?.length > 0 && <div className="banner" style={{ background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)", color: "var(--accent-red)", marginBottom: 16 }}>{summary.errors.map((e: string, i: number) => <div key={i}>{e}</div>)}</div>}

          {/* Distribution outputs */}
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Distribution outputs</div>
          <table className="table" style={{ marginBottom: 24 }}>
            <thead><tr><th>#</th><th>Node</th><th>Formula → resolved</th><th>Export field</th><th style={{ textAlign: "right" }}>Amount</th></tr></thead>
            <tbody>
              {steps.filter((s) => s.type === "distribution").map((s) => (
                <tr key={s.order}>
                  <td style={{ color: "var(--text-muted)" }}>{s.order}</td>
                  <td><span style={{ color: nodeColor.distribution }}>●</span> {s.name}</td>
                  <td><code style={{ fontSize: 12 }}>{s.formula}</code>{s.resolved && <div style={{ fontSize: 11, color: "var(--accent-green)" }}>{s.resolved}</div>}</td>
                  <td>{s.export_field ? <code style={{ color: "var(--accent-purple)", fontSize: 12 }}>{s.export_field}</code> : "—"}</td>
                  <td style={{ textAlign: "right", fontFamily: "monospace", fontWeight: 600 }}>{fmtMoney(s.result)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Validation results */}
          {steps.some((s) => s.type === "validation") && <>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Validation checks</div>
            <table className="table" style={{ marginBottom: 24 }}>
              <thead><tr><th>Check</th><th>Calculated</th><th>Tape</th><th>Difference</th><th>Tolerance</th><th>Result</th></tr></thead>
              <tbody>
                {steps.filter((s) => s.type === "validation").map((s) => (
                  <tr key={s.order} style={s.passed === 0 ? { background: "rgba(248,113,113,0.05)" } : {}}>
                    <td><span style={{ color: nodeColor.validation }}>●</span> {s.name}</td>
                    <td style={{ fontFamily: "monospace" }}>{fmtMoney(s.result)}</td>
                    <td style={{ fontFamily: "monospace" }}>{fmtMoney(s.comparison_value ?? null)}</td>
                    <td style={{ fontFamily: "monospace", color: s.passed === 0 ? "var(--accent-red)" : "var(--text-muted)" }}>{fmtMoney(s.difference)}</td>
                    <td style={{ fontSize: 12, color: "var(--text-muted)" }}>±{s.tolerance}{s.tolerance_type === "percentage" ? "%" : ""}</td>
                    <td>{s.passed === 1 ? <span style={{ color: "var(--accent-green)", fontWeight: 600 }}>Pass</span> : <span style={{ color: "var(--accent-red)", fontWeight: 600 }}>Fail</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>}

          {/* Collapsible full trace */}
          <details>
            <summary style={{ cursor: "pointer", fontWeight: 600, marginBottom: 8 }}>Full execution trace ({steps.length} steps)</summary>
            <table className="table">
              <thead><tr><th>#</th><th>Node</th><th>Type</th><th>Stream</th><th>Formula → resolved</th><th style={{ textAlign: "right" }}>Result</th></tr></thead>
              <tbody>
                {steps.map((s) => (
                  <tr key={s.order}>
                    <td style={{ color: "var(--text-muted)" }}>{s.order}</td>
                    <td><span style={{ color: nodeColor[s.type] }}>●</span> {s.name}</td>
                    <td style={{ fontSize: 12, color: "var(--text-muted)" }}>{s.type.replace("_", " ")}</td>
                    <td><span className={`badge badge-${s.stream === "distribution" ? "active" : "deal"}`} style={{ fontSize: 10 }}>{s.stream}</span></td>
                    <td>{s.formula ? <><code style={{ fontSize: 12 }}>{s.formula}</code>{s.resolved && <div style={{ fontSize: 11, color: "var(--accent-green)" }}>{s.resolved}</div>}</> : "—"}</td>
                    <td style={{ textAlign: "right", fontFamily: "monospace" }}>{s.result != null ? Number(s.result).toLocaleString(undefined, { minimumFractionDigits: 2 }) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </div>
      )}

      {/* Step 5: Waterfall reconciliation */}
      {step === 5 && selectedDeal && run && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ fontWeight: 600, fontSize: 16 }}>Waterfall reconciliation</div>
            <button className="btn btn-secondary btn-sm" onClick={() => goToStep(4)}>← Back to execution</button>
          </div>
          <WaterfallTrace
            dealId={selectedDeal.id}
            runId={run.id}
            onContinue={() => { setMaxStep((m) => Math.max(m, 6)); setStep(6); }}
            onInvestigate={() => goToStep(4)}
          />
        </div>
      )}

      {/* Step 6: Export */}
      {step === 6 && selectedDeal && run && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Select export template</div>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              {exportTemplates.map((t) => (
                <button
                  key={t.id}
                  className={`btn ${selectedTemplateId === t.id ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => { setSelectedTemplateId(t.id); setExportRes(null); }}
                >
                  {t.name}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                {selectedTemplateId ? `Generate CSV using ${exportTemplates.find(t => t.id === selectedTemplateId)?.name ?? "selected template"}` : "Select a template above"}
              </div>
              {!exportRes ? (
                <button className="btn btn-primary" onClick={handleExport} disabled={loading || !selectedTemplateId}>{loading ? "Exporting..." : "Export CSV"}</button>
              ) : (
                <span style={{ color: "var(--accent-green)", fontWeight: 600 }}>✓ Exported</span>
              )}
            </div>
          </div>
          {exportRes && (
            <div className="card" style={{ background: "rgba(74,222,128,0.05)", borderColor: "rgba(74,222,128,0.2)", marginTop: 16 }}>
              <div style={{ fontWeight: 600, color: "var(--accent-green)", marginBottom: 4 }}>✓ CSV exported</div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>File: {exportRes.file_path}<br />SHA-256: <code style={{ fontSize: 11 }}>{exportRes.hash?.slice(0, 24)}...</code></div>
            </div>
          )}
        </div>
      )}

      {/* Remap modal */}
      {remappingVariable && selectedDeal && run && (
        <CellMapperModal
          dealId={selectedDeal.id}
          runId={run.id}
          variableId={remappingVariable.variable_id}
          variableName={remappingVariable.variable_name}
          onClose={() => setRemappingVariable(null)}
          onSaved={async () => {
            if (!remappingVariable.variable_id) return;
            try {
              const updated = await reextractVariable(
                selectedDeal.id,
                run.id,
                remappingVariable.variable_id,
              );
              setVars((prev) =>
                prev.map((v) =>
                  v.variable === remappingVariable.variable_name
                    ? {
                        ...v,
                        variable_id: updated.variable_id,
                        cell: updated.cell,
                        sheet: updated.sheet,
                        raw: updated.raw,
                        parsed: updated.parsed,
                        prior: updated.prior,
                        pct_change: updated.pct_change,
                        warning: updated.warning,
                      }
                    : v,
                ),
              );
            } catch (e: any) {
              setError(e.message);
            }
          }}
        />
      )}
    </div>
  );
}
