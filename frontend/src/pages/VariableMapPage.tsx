import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Variable } from "../types";

interface DealMappingDetail {
  deal_id: number;
  deal_name: string;
  deal_status: string;
  sheet_name: string;
  column_letter: string;
  row_number: number;
  tape_label: string | null;
  alias: string | null;
}

export function VariableMapPage() {
  const [variables, setVariables] = useState<Variable[]>([]);
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [details, setDetails] = useState<DealMappingDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingVars, setLoadingVars] = useState(true);

  useEffect(() => {
    api.get<Variable[]>("/variables/?scope=system").then((sys) => {
      // Load all scopes to get every variable
      Promise.all([
        Promise.resolve(sys),
        api.get<Variable[]>("/variables/?scope=servicer"),
        api.get<Variable[]>("/variables/?scope=deal"),
      ]).then(([s, sv, d]) => {
        const all = [...s, ...sv, ...d];
        // Dedupe by id just in case
        const seen = new Set<number>();
        const unique = all.filter((v) => {
          if (seen.has(v.id)) return false;
          seen.add(v.id);
          return true;
        });
        unique.sort((a, b) => a.name.localeCompare(b.name));
        setVariables(unique);
      }).finally(() => setLoadingVars(false));
    });
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetails([]);
      return;
    }
    setLoading(true);
    api.get<DealMappingDetail[]>(`/variables/${selectedId}/deal-detail`)
      .then(setDetails)
      .finally(() => setLoading(false));
  }, [selectedId]);

  const selectedVar = variables.find((v) => v.id === selectedId) ?? null;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Variable Map</div>
          <div className="page-subtitle">
            View which deals use a variable, along with mapping details and deal-level aliases
          </div>
        </div>
      </div>

      {/* Variable selector */}
      <div style={{ marginBottom: 24 }}>
        <label className="form-label" style={{ marginBottom: 6 }}>Select a variable</label>
        <select
          className="select"
          style={{ width: 420 }}
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : "")}
          disabled={loadingVars}
        >
          <option value="">{loadingVars ? "Loading variables…" : "Choose a variable…"}</option>
          {variables.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}{v.display_name ? ` — ${v.display_name}` : ""} ({v.scope})
            </option>
          ))}
        </select>
      </div>

      {/* Selected variable info */}
      {selectedVar && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 16,
            marginBottom: 24,
            padding: 16,
            background: "var(--surface-secondary)",
            borderRadius: 8,
            border: "1px solid var(--border)",
          }}
        >
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>Name</div>
            <code style={{ color: "var(--accent-green)", fontSize: 14 }}>{selectedVar.name}</code>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>Display name</div>
            <div style={{ fontSize: 14 }}>{selectedVar.display_name ?? "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>Type</div>
            <div style={{ fontSize: 14 }}>{selectedVar.data_type}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>Scope</div>
            <span className={`badge badge-${selectedVar.scope}`}>{selectedVar.scope}</span>
          </div>
          {selectedVar.description && (
            <div style={{ gridColumn: "1 / -1" }}>
              <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 4 }}>Description</div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{selectedVar.description}</div>
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {!selectedId && (
        <div className="empty-state">
          <div className="empty-state-icon">🗺️</div>
          <div className="empty-state-title">Select a variable</div>
          <div className="empty-state-text">
            Pick a variable from the dropdown to see all deals where it is mapped.
          </div>
        </div>
      )}

      {selectedId && loading && (
        <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>Loading…</div>
      )}

      {selectedId && !loading && details.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📭</div>
          <div className="empty-state-title">Not mapped in any deal</div>
          <div className="empty-state-text">
            This variable has no tape mappings in any deal yet.
          </div>
        </div>
      )}

      {selectedId && !loading && details.length > 0 && (
        <>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 8 }}>
            Mapped in <strong style={{ color: "var(--text-primary)" }}>{details.length}</strong> deal{details.length !== 1 ? "s" : ""}
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Deal</th>
                <th>Status</th>
                <th>Sheet</th>
                <th>Cell</th>
                <th>Tape label</th>
                <th>Deal alias</th>
              </tr>
            </thead>
            <tbody>
              {details.map((d) => (
                <tr key={d.deal_id}>
                  <td>
                    <Link to={`/deals/${d.deal_id}`} style={{ color: "var(--accent-blue)", textDecoration: "none", fontWeight: 500 }}>
                      {d.deal_name}
                    </Link>
                  </td>
                  <td>
                    <span className={`badge badge-${d.deal_status}`}>{d.deal_status}</span>
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 13 }}>{d.sheet_name}</td>
                  <td style={{ fontFamily: "monospace", fontSize: 13 }}>{d.column_letter}{d.row_number}</td>
                  <td style={{ color: d.tape_label ? "var(--text-primary)" : "var(--text-muted)" }}>
                    {d.tape_label ?? "—"}
                  </td>
                  <td style={{ color: d.alias ? "var(--accent-purple)" : "var(--text-muted)" }}>
                    {d.alias ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
