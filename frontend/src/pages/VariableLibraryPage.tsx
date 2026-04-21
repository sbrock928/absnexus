import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useConfirm } from "../components/ConfirmDialog";
import type { Variable, Servicer } from "../types";

const DATA_TYPES = ["decimal", "percentage", "integer", "string", "date"];

export function VariableLibraryPage() {
  const { isModeler } = useAuth();
  const confirm = useConfirm();
  const [vars, setVars] = useState<Variable[]>([]);
  const [servicers, setServicers] = useState<Servicer[]>([]);
  const [scope, setScope] = useState("system");
  const [servicerFilter, setServicerFilter] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editingVar, setEditingVar] = useState<Variable | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = () => {
    setLoading(true);
    let url = `/variables/?scope=${scope}`;
    if (scope === "servicer" && servicerFilter) url += `&servicer_id=${servicerFilter}`;
    Promise.all([
      api.get<Variable[]>(url),
      api.get<Servicer[]>("/servicers/"),
    ]).then(([v, s]) => {
      setVars(v);
      setServicers(s);
    }).finally(() => setLoading(false));
  };

  useEffect(reload, [scope, servicerFilter]);

  const handleDelete = async (v: Variable) => {
    if (!(await confirm({ message: `Delete variable "${v.name}"?`, confirmLabel: "Delete" }))) return;
    await api.del(`/variables/${v.id}`);
    reload();
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Variable Library</div>
          <div className="page-subtitle">
            Canonical variable definitions with 3-tier scope resolution
          </div>
        </div>
        {isModeler && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New variable</button>
        )}
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20 }}>
        <div className="tabs" style={{ marginBottom: 0 }}>
          {["system", "servicer", "deal"].map((s) => (
            <button key={s} className={`tab ${scope === s ? "active" : ""}`} onClick={() => { setScope(s); setServicerFilter(null); }}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {scope === "servicer" && (
          <select
            className="select"
            style={{ width: 200 }}
            value={servicerFilter ?? ""}
            onChange={(e) => setServicerFilter(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">All servicers</option>
            {servicers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        )}
      </div>

      {vars.length === 0 && !loading ? (
        <div className="empty-state">
          <div className="empty-state-icon">🔤</div>
          <div className="empty-state-title">No {scope} variables</div>
          <div className="empty-state-text">
            {scope === "system"
              ? "System variables are shared across all deals and servicers."
              : scope === "servicer"
              ? "Servicer variables override system variables for a specific servicer."
              : "Deal variables override system and servicer variables for a specific deal."}
          </div>
          {isModeler && (
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New variable</button>
          )}
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Display name</th>
              <th>Type</th>
              <th>Scope</th>
              <th>Description</th>
              {isModeler && <th style={{ width: 100 }}></th>}
            </tr>
          </thead>
          <tbody>
            {vars.map((v) => (
              <tr key={v.id}>
                <td><code style={{ color: "var(--accent-green)", fontSize: 13 }}>{v.name}</code></td>
                <td>{v.display_name ?? "—"}</td>
                <td style={{ color: "var(--text-muted)" }}>{v.data_type}</td>
                <td><span className={`badge badge-${v.scope}`}>{v.scope}</span></td>
                <td style={{ color: "var(--text-muted)", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {v.description ?? "—"}
                </td>
                {isModeler && (
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setEditingVar(v)}>Edit</button>
                      <button className="btn btn-ghost btn-sm" style={{ color: "var(--accent-red)" }} onClick={() => handleDelete(v)}>Delete</button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showCreate && (
        <CreateVariableDialog
          servicers={servicers}
          defaultScope={scope}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload(); }}
        />
      )}
      {editingVar && (
        <EditVariableDialog
          variable={editingVar}
          onClose={() => setEditingVar(null)}
          onSaved={() => { setEditingVar(null); reload(); }}
        />
      )}
    </div>
  );
}

function CreateVariableDialog({
  servicers, defaultScope, onClose, onCreated,
}: {
  servicers: Servicer[]; defaultScope: string; onClose: () => void; onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [dataType, setDataType] = useState("decimal");
  const [varScope, setVarScope] = useState(defaultScope);
  const [servicerId, setServicerId] = useState<number | "">(servicers[0]?.id ?? "");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    const cleanName = name.trim().toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
    if (!cleanName) { setError("Variable name is required"); return; }
    if (varScope === "servicer" && !servicerId) { setError("Select a servicer for servicer-scoped variables"); return; }
    setSaving(true); setError("");
    try {
      await api.post("/variables/", {
        name: cleanName,
        display_name: displayName.trim() || null,
        data_type: dataType,
        scope: varScope,
        servicer_id: varScope === "servicer" ? servicerId : null,
        description: description.trim() || null,
      });
      onCreated();
    } catch (e: any) { setError(e.message || "Failed to create variable"); }
    finally { setSaving(false); }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 500 }}>
        <div className="dialog-title">Create new variable</div>
        {error && <div className="banner banner-warn" style={{ marginBottom: 16 }}>{error}</div>}

        <div className="form-row">
          <div className="form-field" style={{ flex: 2 }}>
            <label className="form-label">Canonical name</label>
            <input
              className="input"
              placeholder="e.g. total_collections"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
            />
            <div className="form-help">Lowercase with underscores. Used in formulas.</div>
          </div>
          <div className="form-field" style={{ flex: 1 }}>
            <label className="form-label">Data type</label>
            <select className="select" value={dataType} onChange={(e) => setDataType(e.target.value)}>
              {DATA_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div className="form-field">
          <label className="form-label">Display name (optional)</label>
          <input className="input" placeholder="e.g. Total Monthly Collections" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </div>

        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Scope</label>
            <select className="select" value={varScope} onChange={(e) => setVarScope(e.target.value)}>
              <option value="system">System (all deals)</option>
              <option value="servicer">Servicer</option>
              <option value="deal">Deal</option>
            </select>
          </div>
          {varScope === "servicer" && (
            <div className="form-field">
              <label className="form-label">Servicer</label>
              <select className="select" value={servicerId} onChange={(e) => setServicerId(Number(e.target.value))}>
                {servicers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="form-field">
          <label className="form-label">Description (optional)</label>
          <textarea className="textarea" placeholder="What does this variable represent?" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>{saving ? "Creating..." : "Create variable"}</button>
        </div>
      </div>
    </div>
  );
}

function EditVariableDialog({ variable, onClose, onSaved }: { variable: Variable; onClose: () => void; onSaved: () => void }) {
  const [displayName, setDisplayName] = useState(variable.display_name ?? "");
  const [dataType, setDataType] = useState(variable.data_type);
  const [description, setDescription] = useState(variable.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    setSaving(true); setError("");
    try {
      await api.patch(`/variables/${variable.id}`, {
        display_name: displayName.trim() || null,
        data_type: dataType,
        description: description.trim() || null,
      });
      onSaved();
    } catch (e: any) { setError(e.message || "Failed to update variable"); }
    finally { setSaving(false); }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 460 }}>
        <div className="dialog-title">
          Edit variable: <code style={{ color: "var(--accent-green)" }}>{variable.name}</code>
        </div>
        {error && <div className="banner banner-warn" style={{ marginBottom: 16 }}>{error}</div>}

        <div className="banner banner-info" style={{ marginBottom: 16 }}>
          Canonical name and scope cannot be changed after creation.
        </div>

        <div className="form-row">
          <div className="form-field" style={{ flex: 2 }}>
            <label className="form-label">Display name</label>
            <input className="input" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Human-readable label" />
          </div>
          <div className="form-field" style={{ flex: 1 }}>
            <label className="form-label">Data type</label>
            <select className="select" value={dataType} onChange={(e) => setDataType(e.target.value)}>
              {DATA_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div className="form-field">
          <label className="form-label">Description</label>
          <textarea className="textarea" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>{saving ? "Saving..." : "Save changes"}</button>
        </div>
      </div>
    </div>
  );
}

