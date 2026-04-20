import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";

/*
 * PreviewPanel — collapsible right-side panel for live DAG authoring.
 *
 * Picks an existing completed run as the "fixture" (tape data source) and
 * calls POST /deals/{id}/preview-execution with the current DAG. The backend
 * rolls back the preview transaction so nothing persists. React Query
 * invalidation is wired at the call site, so the panel auto-refreshes
 * after every formula / waterfall / validation mutation.
 */

interface PreviewStep {
  order: number;
  key: string;
  name: string;
  type: string;
  stream: string;
  formula: string | null;
  resolved: string | null;
  result: string | null;
  export_field: string | null;
  comparison_value: string | null;
  comparison_variable: string | null;
  tolerance: string | null;
  tolerance_type: string | null;
  passed: number | null;
  difference: string | null;
}

interface PreviewResponse {
  source_run_id: number;
  source_period: string;
  validations_passed: number;
  validations_total: number;
  total_distribution: string;
  errors: string[];
  steps: PreviewStep[];
}

interface RunSummary {
  id: number;
  report_period: string;
  status: string;
  total_distribution: string | null;
  validations_passed: number | null;
  validations_total: number | null;
}

interface Props {
  dealId: number;
  open: boolean;
  onToggle: () => void;
}

const STORAGE_KEY = "absnexus.preview.sourceRunId";

function fmtMoney(v: string | null): string {
  if (!v) return "—";
  const n = Number(v);
  if (isNaN(n)) return v;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

function fmtByType(v: string | null, type: string): string {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (isNaN(n)) return v;
  // Validations comparing days/percentages are rare — default money for results.
  if (type === "validation" && Math.abs(n) < 1000 && Math.abs(n - Math.round(n)) < 1e-9) {
    return String(Math.round(n));
  }
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}

export function PreviewPanel({ dealId, open, onToggle }: Props) {
  const [sourceRunId, setSourceRunId] = useState<number | null>(() => {
    const stored = localStorage.getItem(`${STORAGE_KEY}.${dealId}`);
    return stored ? Number(stored) : null;
  });

  // Available completed runs for this deal (the fixture options).
  const { data: runs = [] } = useQuery<RunSummary[]>({
    queryKey: ["deal-runs", dealId],
    queryFn: () => api.get(`/deals/${dealId}/runs`),
    enabled: open,
  });

  // Pick the most recent completed run by default if nothing stored.
  useEffect(() => {
    if (sourceRunId === null && runs.length > 0) {
      const firstCompleted = runs.find(
        (r) => r.status === "completed" || r.status === "executed",
      );
      if (firstCompleted) {
        setSourceRunId(firstCompleted.id);
        localStorage.setItem(`${STORAGE_KEY}.${dealId}`, String(firstCompleted.id));
      }
    }
  }, [runs, sourceRunId, dealId]);

  // Preview query — runs automatically when any mutation invalidates it.
  // Callers (DagEditorPage etc) invalidate `["preview", dealId]` after mutations.
  const {
    data: preview,
    isFetching,
    error,
  } = useQuery<PreviewResponse>({
    queryKey: ["preview", dealId, sourceRunId],
    queryFn: () =>
      api.post(`/deals/${dealId}/preview-execution`, {
        source_run_id: sourceRunId,
      }),
    enabled: open && sourceRunId !== null,
    staleTime: 0, // always refetch on invalidation
  });

  const handlePickRun = (id: number) => {
    setSourceRunId(id);
    localStorage.setItem(`${STORAGE_KEY}.${dealId}`, String(id));
  };

  const distributionSteps = useMemo(
    () => (preview?.steps ?? []).filter((s) => s.type === "distribution"),
    [preview],
  );
  const validationSteps = useMemo(
    () => (preview?.steps ?? []).filter((s) => s.type === "validation"),
    [preview],
  );
  const calcSteps = useMemo(
    () => (preview?.steps ?? []).filter((s) => s.type === "calculation"),
    [preview],
  );

  // Collapsed — thin rail on the right.
  if (!open) {
    return (
      <button
        type="button"
        onClick={onToggle}
        title="Open live preview"
        style={{
          position: "fixed",
          right: 0,
          top: 120,
          zIndex: 40,
          writingMode: "vertical-rl",
          transform: "rotate(180deg)",
          padding: "12px 6px",
          fontSize: 12,
          fontWeight: 600,
          background: "var(--bg-secondary)",
          border: "1px solid var(--border-color)",
          borderRight: "none",
          borderRadius: "6px 0 0 6px",
          color: "var(--accent-blue)",
          cursor: "pointer",
          boxShadow: "-4px 0 12px rgba(0,0,0,0.2)",
        }}
      >
        ▸ Live preview
      </button>
    );
  }

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        bottom: 0,
        width: "min(520px, 45vw)",
        background: "var(--bg-primary)",
        borderLeft: "1px solid var(--border-color)",
        boxShadow: "-8px 0 24px rgba(0,0,0,0.3)",
        zIndex: 40,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid var(--border-color)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: 0.5,
            }}
          >
            Live preview {isFetching && "· refreshing…"}
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>
            Runs against prior tape · no DB writes
          </div>
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="btn btn-secondary btn-sm"
          style={{ padding: "4px 10px" }}
        >
          Collapse
        </button>
      </div>

      {/* Source run picker */}
      <div
        style={{
          padding: "10px 16px",
          borderBottom: "1px solid var(--border-color)",
          background: "var(--bg-secondary)",
        }}
      >
        <label
          style={{ fontSize: 11, color: "var(--text-muted)", display: "block", marginBottom: 4 }}
        >
          Tape fixture (completed run)
        </label>
        {runs.length === 0 ? (
          <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic" }}>
            No completed runs for this deal — run one through the Processing wizard first.
          </div>
        ) : (
          <select
            value={sourceRunId ?? ""}
            onChange={(e) => handlePickRun(Number(e.target.value))}
            style={{
              width: "100%",
              padding: "5px 8px",
              background: "var(--bg-primary)",
              border: "1px solid var(--border-color)",
              borderRadius: 4,
              color: "var(--text-primary)",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
            }}
          >
            {runs
              .filter((r) => r.status === "completed" || r.status === "executed")
              .map((r) => (
                <option key={r.id} value={r.id}>
                  RUN-{r.id} · {r.report_period} · {r.validations_passed ?? "?"}/
                  {r.validations_total ?? "?"} val
                </option>
              ))}
          </select>
        )}
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: "auto", padding: "10px 16px" }}>
        {error && (
          <div
            style={{
              padding: 10,
              background: "rgba(248,113,113,0.1)",
              border: "1px solid rgba(248,113,113,0.3)",
              borderRadius: 4,
              color: "var(--accent-red)",
              fontSize: 12,
              marginBottom: 12,
            }}
          >
            {String((error as Error)?.message ?? error)}
          </div>
        )}

        {preview && (
          <>
            {/* Summary pills */}
            <div
              style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}
            >
              <div
                style={{
                  padding: 8,
                  background: "var(--bg-secondary)",
                  borderRadius: 4,
                  border: "1px solid var(--border-color)",
                }}
              >
                <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Validations
                </div>
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 600,
                    color:
                      preview.validations_passed === preview.validations_total
                        ? "var(--accent-green)"
                        : "var(--accent-red)",
                  }}
                >
                  {preview.validations_passed}/{preview.validations_total}
                </div>
              </div>
              <div
                style={{
                  padding: 8,
                  background: "var(--bg-secondary)",
                  borderRadius: 4,
                  border: "1px solid var(--border-color)",
                }}
              >
                <div style={{ fontSize: 10, color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Total distribution
                </div>
                <div style={{ fontSize: 18, fontWeight: 600, fontFamily: "var(--font-mono)" }}>
                  {fmtMoney(preview.total_distribution)}
                </div>
              </div>
            </div>

            {preview.errors.length > 0 && (
              <div
                style={{
                  padding: 8,
                  background: "rgba(251,191,36,0.1)",
                  border: "1px solid rgba(251,191,36,0.3)",
                  borderRadius: 4,
                  fontSize: 11,
                  color: "var(--accent-yellow)",
                  marginBottom: 12,
                  fontFamily: "var(--font-mono)",
                }}
              >
                {preview.errors.slice(0, 5).map((e, i) => (
                  <div key={i}>{e}</div>
                ))}
                {preview.errors.length > 5 && (
                  <div>+{preview.errors.length - 5} more…</div>
                )}
              </div>
            )}

            {/* Validation results (most important signal) */}
            {validationSteps.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                  Validation checks
                </div>
                <table className="table" style={{ fontSize: 11 }}>
                  <thead>
                    <tr>
                      <th style={{ width: "40%" }}>Check</th>
                      <th style={{ textAlign: "right" }}>Calc</th>
                      <th style={{ textAlign: "right" }}>Tape</th>
                      <th style={{ width: 50, textAlign: "center" }}>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {validationSteps.map((s) => (
                      <tr
                        key={s.key}
                        style={s.passed === 0 ? { background: "rgba(248,113,113,0.05)" } : {}}
                      >
                        <td>
                          <div style={{ fontWeight: 500 }}>{s.name}</div>
                          <div
                            style={{
                              fontSize: 10,
                              color: "var(--text-muted)",
                              fontFamily: "var(--font-mono)",
                            }}
                          >
                            {s.key}
                          </div>
                        </td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                          {fmtByType(s.result, "validation")}
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            fontFamily: "var(--font-mono)",
                            color: "var(--text-muted)",
                          }}
                        >
                          {fmtByType(s.comparison_value, "validation")}
                        </td>
                        <td style={{ textAlign: "center" }}>
                          {s.passed === 1 && (
                            <span style={{ color: "var(--accent-green)", fontWeight: 600 }}>
                              ✓
                            </span>
                          )}
                          {s.passed === 0 && (
                            <span style={{ color: "var(--accent-red)", fontWeight: 600 }}>
                              ✗
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Distribution outputs */}
            {distributionSteps.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                  Distributions
                </div>
                <table className="table" style={{ fontSize: 11 }}>
                  <thead>
                    <tr>
                      <th>Node</th>
                      <th style={{ textAlign: "right" }}>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {distributionSteps.map((s) => (
                      <tr key={s.key}>
                        <td>
                          <div style={{ fontWeight: 500 }}>{s.name}</div>
                          <div
                            style={{
                              fontSize: 10,
                              color: "var(--text-muted)",
                              fontFamily: "var(--font-mono)",
                            }}
                          >
                            {s.key}
                          </div>
                        </td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                          {fmtMoney(s.result)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Calculations (collapsed by default) */}
            {calcSteps.length > 0 && (
              <details>
                <summary
                  style={{
                    cursor: "pointer",
                    fontSize: 12,
                    fontWeight: 600,
                    marginBottom: 6,
                  }}
                >
                  Calculations ({calcSteps.length})
                </summary>
                <table className="table" style={{ fontSize: 11, marginTop: 6 }}>
                  <tbody>
                    {calcSteps.map((s) => (
                      <tr key={s.key}>
                        <td>
                          <div style={{ fontWeight: 500 }}>{s.name}</div>
                          <div
                            style={{
                              fontSize: 10,
                              color: "var(--text-muted)",
                              fontFamily: "var(--font-mono)",
                            }}
                          >
                            {s.key}
                          </div>
                        </td>
                        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                          {fmtMoney(s.result)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
          </>
        )}

        {!preview && sourceRunId !== null && !isFetching && !error && (
          <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic" }}>
            Loading preview…
          </div>
        )}
      </div>
    </div>
  );
}
