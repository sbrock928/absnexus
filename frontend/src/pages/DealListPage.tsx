import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { useToast } from "../components/Toast";
import { useConfirm } from "../components/ConfirmDialog";
import { api } from "../api/client";
import type { Deal, Servicer } from "../types";

const PRODUCT_TYPES = ["ABS Auto", "ABS Consumer", "MBS HELOC", "MBS Residential", "CRT", "CLO"];

const VALID_TRANSITIONS: Record<string, string[]> = {
  draft: ["draft", "active"],
  active: ["active", "archived"],
  archived: ["archived", "active"],
};

export function DealListPage() {
  const { isModeler, isAnalyst } = useAuth();
  const { toast } = useToast();
  const confirm = useConfirm();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [servicers, setServicers] = useState<Servicer[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [editingDeal, setEditingDeal] = useState<Deal | null>(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const reload = () => {
    setLoading(true);
    const dealsUrl = isAnalyst ? "/deals/?exclude_status=draft" : "/deals/";
    Promise.all([
      api.get<Deal[]>(dealsUrl),
      api.get<Servicer[]>("/servicers/"),
    ]).then(([d, s]) => { setDeals(d); setServicers(s); })
      .finally(() => setLoading(false));
  };

  useEffect(reload, [isAnalyst]);

  const filtered = filter === "all" ? deals : deals.filter((d) => d.status === filter);
  const counts: Record<string, number> = {
    all: deals.length,
    active: deals.filter((d) => d.status === "active").length,
    draft: deals.filter((d) => d.status === "draft").length,
    archived: deals.filter((d) => d.status === "archived").length,
  };

  const tabs = isAnalyst
    ? (["all", "active", "archived"] as const)
    : (["all", "active", "draft", "archived"] as const);

  const handleDelete = async (deal: Deal) => {
    if (!(await confirm({ message: `Delete "${deal.name}"? This cannot be undone.`, confirmLabel: "Delete" }))) return;
    try {
      await api.del(`/deals/${deal.id}`);
      toast("Deal deleted");
      reload();
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Failed to delete deal", "error");
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Deals</div>
          <div className="page-subtitle">{deals.length} deal{deals.length !== 1 ? "s" : ""}</div>
        </div>
        {isModeler && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New deal</button>
        )}
      </div>

      {isAnalyst && (
        <div className="banner banner-info">
          You have read-only access. Contact an analytics team member to create or edit deals.
        </div>
      )}

      <div className="tabs">
        {tabs.map((f) => (
          <button key={f} className={`tab ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)} ({counts[f]})
          </button>
        ))}
      </div>

      {filtered.length === 0 && !loading ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-title">
            {filter === "all" ? "No deals yet" : `No ${filter} deals`}
          </div>
          <div className="empty-state-text">
            {filter === "all" && isModeler
              ? "Create your first deal to get started."
              : filter !== "all" ? "Try switching to a different filter." : "No deals have been configured yet."}
          </div>
          {filter === "all" && isModeler && (
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New deal</button>
          )}
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Deal</th><th>Servicer</th><th>Product</th><th>Status</th><th>Updated</th>
              {isModeler && <th style={{ width: 120 }}></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map((d) => (
              <tr key={d.id}>
                <td><Link to={`/deals/${d.id}`} style={{ color: "var(--accent-blue)", textDecoration: "none" }}>{d.name}</Link></td>
                <td>{servicers.find((s) => s.id === d.servicer_id)?.name ?? "—"}</td>
                <td>{d.product_type}</td>
                <td><span className={`badge badge-${d.status}`}>{d.status}</span></td>
                <td style={{ color: "var(--text-muted)" }}>{new Date(d.updated_at).toLocaleDateString()}</td>
                {isModeler && (
                  <td>
                    <div className="row-actions">
                      <button className="btn btn-ghost btn-sm" onClick={() => setEditingDeal(d)}>Edit</button>
                      <button className="btn btn-ghost btn-sm" style={{ color: "var(--accent-red)" }} onClick={() => handleDelete(d)}>Delete</button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showCreate && (
        <CreateDealDialog servicers={servicers} onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); reload(); }} />
      )}
      {editingDeal && (
        <EditDealDialog deal={editingDeal} onClose={() => setEditingDeal(null)} onSaved={() => { setEditingDeal(null); reload(); }} />
      )}
    </div>
  );
}

function CreateDealDialog({ servicers, onClose, onCreated }: { servicers: Servicer[]; onClose: () => void; onCreated: () => void }) {
  const { toast } = useToast();
  const [name, setName] = useState("");
  const [servicerId, setServicerId] = useState(servicers[0]?.id ?? 0);
  const [productType, setProductType] = useState(PRODUCT_TYPES[0]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!name.trim()) { setError("Deal name is required"); return; }
    if (!servicerId) { setError("Select a servicer"); return; }
    setSaving(true); setError("");
    try {
      await api.post("/deals/", { name: name.trim(), servicer_id: servicerId, product_type: productType });
      toast("Deal created");
      onCreated();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to create deal"); }
    finally { setSaving(false); }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 460 }}>
        <div className="dialog-title">Create new deal</div>
        {error && <div className="banner banner-warn" style={{ marginBottom: 16 }}>{error}</div>}
        <div className="form-field">
          <label className="form-label">Deal name</label>
          <input className="input" placeholder="e.g. AMORT 2025-1" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Servicer</label>
            <select className="select" value={servicerId} onChange={(e) => setServicerId(Number(e.target.value))}>
              {servicers.length === 0 && <option value={0}>No servicers configured</option>}
              {servicers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Product type</label>
            <select className="select" value={productType} onChange={(e) => setProductType(e.target.value)}>
              {PRODUCT_TYPES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>
        <div className="form-help">The deal will be created in Draft status. Configure variable mappings and DAG before activating.</div>
        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>{saving ? "Creating..." : "Create deal"}</button>
        </div>
      </div>
    </div>
  );
}

function EditDealDialog({ deal, onClose, onSaved }: { deal: Deal; onClose: () => void; onSaved: () => void }) {
  const { toast } = useToast();
  const [name, setName] = useState(deal.name);
  const [productType, setProductType] = useState(deal.product_type);
  const [status, setStatus] = useState(deal.status);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const allowedStatuses = VALID_TRANSITIONS[deal.status] || [deal.status];

  const handleSubmit = async () => {
    if (!name.trim()) { setError("Deal name is required"); return; }
    setSaving(true); setError("");
    try {
      await api.patch(`/deals/${deal.id}`, { name: name.trim(), product_type: productType, status });
      toast("Deal updated");
      onSaved();
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to update deal"); }
    finally { setSaving(false); }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 460 }}>
        <div className="dialog-title">Edit deal</div>
        {error && <div className="banner banner-warn" style={{ marginBottom: 16 }}>{error}</div>}
        <div className="form-field">
          <label className="form-label">Deal name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Product type</label>
            <select className="select" value={productType} onChange={(e) => setProductType(e.target.value)}>
              {PRODUCT_TYPES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Status</label>
            <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
              {allowedStatuses.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
            </select>
          </div>
        </div>
        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={saving}>{saving ? "Saving..." : "Save changes"}</button>
        </div>
      </div>
    </div>
  );
}
