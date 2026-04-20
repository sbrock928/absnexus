import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth";
import { useToast } from "../components/Toast";
import { api } from "../api/client";
import { PreviewPanel } from "../components/preview/PreviewPanel";
import {
  listTemplates,
  getTemplate,
  getDealExportConfig,
  type GlobalTemplate,
  type GlobalColumn,
  type DealExportRow,
} from "../api/globalExport";
import type { Deal, Servicer, Variable } from "../types";
import { WaterfallTrace } from "../components/processing/WaterfallTrace";
import { DealInfoTab } from "../components/deal/DealInfoTab";
import { ValidationsTab } from "../components/deal/ValidationsTab";

interface MappingVariable {
  id: number;
  name: string;
  display_name: string | null;
}

interface Mapping {
  id: number;
  variable_id: number;
  variable: MappingVariable | null;
  sheet_name: string;
  column_letter: string;
  row_number: number;
  tape_label: string | null;
}

interface Tranche {
  id: number;
  class_label: string;
  cusip: string | null;
  regulation_type: string;
  note_rate: number | null;
  original_balance: number | null;
  maturity_date: string | null;
  is_active: boolean;
}

interface Alias {
  id: number;
  variable_id: number;
  servicer_id: number | null;
  deal_id: number | null;
  display_alias: string;
}

interface DagData {
  version: { id: number; version_number: number; description: string | null; created_by: string; created_at: string };
  nodes: Array<{ id: number; key: string; name: string; node_type: string; stream: string; formula: string | null; export_field: string | null; comparison_variable: string | null; tolerance: number | null }>;
  edges: Array<{ id: number; source_node_id: number; target_node_id: number }>;
}

export function DealDetailPage() {
  const { dealId } = useParams<{ dealId: string }>();
  const { isModeler, isAnalyst } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [deal, setDeal] = useState<Deal | null>(null);
  const [servicer, setServicer] = useState<Servicer | null>(null);
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [tranches, setTranches] = useState<Tranche[]>([]);
  const [dag, setDag] = useState<DagData | null>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [exportTemplates, setExportTemplates] = useState<GlobalTemplate[]>([]);
  const [activeExportTemplateId, setActiveExportTemplateId] = useState<number | null>(null);
  const [exportTemplateColumns, setExportTemplateColumns] = useState<GlobalColumn[]>([]);
  const [exportDealRows, setExportDealRows] = useState<DealExportRow[]>([]);
  const [variables, setVariables] = useState<Variable[]>([]);
  const [tab, setTab] = useState("overview");
  const [showClone, setShowClone] = useState(false);
  const [error, setError] = useState("");

  // Mapping dialog state
  const [showMappingDialog, setShowMappingDialog] = useState(false);
  const [editingMapping, setEditingMapping] = useState<Mapping | null>(null);

  // Tranche dialog state
  const [showTrancheDialog, setShowTrancheDialog] = useState(false);
  const [editingTranche, setEditingTranche] = useState<Tranche | null>(null);

  // Alias state
  const [dealAliases, setDealAliases] = useState<Record<number, string>>({});
  const [editingAliasVarId, setEditingAliasVarId] = useState<number | null>(null);
  const [aliasInput, setAliasInput] = useState("");

  const reloadMappings = () => { if (dealId) api.get<Mapping[]>(`/deals/${dealId}/mappings`).then(setMappings); };
  const reloadTranches = () => { if (dealId) api.get<Tranche[]>(`/deals/${dealId}/tranches`).then(setTranches); };
  const reloadDag = () => { if (dealId) api.get<DagData>(`/deals/${dealId}/dag`).then(setDag).catch(() => {}); };
  const reloadAliases = () => {
    if (!dealId) return;
    // Load aliases for all variables mapped in this deal
    const varIds = [...new Set(mappings.map((m) => m.variable_id))];
    Promise.all(varIds.map((vid) => api.get<Alias[]>(`/variables/${vid}/aliases`))).then((results) => {
      const map: Record<number, string> = {};
      results.forEach((aliases, i) => {
        const dealAlias = aliases.find((a) => a.deal_id === Number(dealId));
        if (dealAlias) map[varIds[i]] = dealAlias.display_alias;
      });
      setDealAliases(map);
    });
  };

  useEffect(() => {
    if (!dealId) return;
    api.get<Deal>(`/deals/${dealId}`).then(setDeal).catch(() => setError("Deal not found"));
    reloadMappings();
    reloadTranches();
    api.get<DagData>(`/deals/${dealId}/dag`).then(setDag).catch(() => {});
    api.get<any[]>(`/deals/${dealId}/runs`).then(setRuns).catch(() => {});
    api.get<Variable[]>(`/variables/available/${dealId}`).then(setVariables).catch(() => {});
    listTemplates().then((templates) => {
      setExportTemplates(templates);
      if (templates.length > 0) setActiveExportTemplateId(templates[0].id);
    }).catch(() => {});
  }, [dealId]);

  // Load export template columns + deal mappings when active template changes
  useEffect(() => {
    if (!dealId || !activeExportTemplateId) return;
    getTemplate(activeExportTemplateId).then((data) => {
      setExportTemplateColumns(data.columns);
    }).catch(() => setExportTemplateColumns([]));
    getDealExportConfig(Number(dealId), activeExportTemplateId).then((cfg) => setExportDealRows(cfg.rows)).catch(() => setExportDealRows([]));
  }, [dealId, activeExportTemplateId]);

  // Reload aliases whenever mappings change
  useEffect(() => {
    if (mappings.length > 0) reloadAliases();
  }, [mappings, dealId]);

  const handleSaveAlias = async (variableId: number, alias: string) => {
    try {
      await api.put(`/variables/${variableId}/aliases`, {
        display_alias: alias.trim(),
        deal_id: Number(dealId),
      });
      toast("Alias saved");
      reloadAliases();
      setEditingAliasVarId(null);
    } catch (e: unknown) { toast(e instanceof Error ? e.message : "Failed to save alias", "error"); }
  };

  const handleClearAlias = async (variableId: number) => {
    // Find and delete the deal alias
    const aliases = await api.get<Alias[]>(`/variables/${variableId}/aliases`);
    const dealAlias = aliases.find((a) => a.deal_id === Number(dealId));
    if (dealAlias) {
      await api.del(`/variables/${variableId}/aliases/${dealAlias.id}`);
    }
    reloadAliases();
    setEditingAliasVarId(null);
  };

  useEffect(() => {
    if (deal) {
      api.get<Servicer[]>("/servicers/").then((svcs) => {
        setServicer(svcs.find((s) => s.id === deal.servicer_id) ?? null);
      });
    }
  }, [deal]);

  const handleDeleteMapping = async (m: Mapping) => {
    if (!confirm(`Delete mapping for ${m.tape_label || `var_${m.variable_id}`}?`)) return;
    try {
      await api.del(`/deals/${dealId}/mappings/${m.id}`);
      toast("Mapping deleted");
      reloadMappings();
    } catch (e: unknown) { toast(e instanceof Error ? e.message : "Failed to delete", "error"); }
  };

  const handleDeleteTranche = async (t: Tranche) => {
    if (!confirm(`Delete tranche Class ${t.class_label}?`)) return;
    try {
      await api.del(`/deals/${dealId}/tranches/${t.id}`);
      toast("Tranche deleted");
      reloadTranches();
    } catch (e: unknown) { toast(e instanceof Error ? e.message : "Failed to delete", "error"); }
  };

  if (error) return <div style={{ padding: 40, color: "var(--accent-red)" }}>{error}</div>;
  if (!deal) return <div style={{ padding: 40, color: "var(--text-muted)" }}>Loading...</div>;

  const isArchived = deal.status === "archived";
  const isEditable = isModeler && !isArchived;

  const handleReactivate = async () => {
    try {
      const updated = await api.patch<Deal>(`/deals/${deal.id}`, { status: "active" });
      setDeal(updated);
      toast("Deal reactivated");
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Failed to reactivate", "error");
    }
  };

  const nodeColor: Record<string, string> = {
    input_value: "var(--accent-green)",
    calculation: "var(--accent-blue)",
    distribution: "var(--accent-purple)",
    validation: "var(--accent-orange)",
  };

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
        <Link to="/deals" style={{ color: "var(--accent-blue)", textDecoration: "none" }}>Deals</Link>
        {" / "}{deal.name}
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">{deal.name}</div>
          <div className="page-subtitle">
            {servicer?.name ?? "—"} · {deal.product_type} · <span className={`badge badge-${deal.status}`}>{deal.status}</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {isEditable && <button className="btn btn-secondary" onClick={() => setShowClone(true)}>Clone deal</button>}
          {isEditable && <Link to={`/deals/${dealId}/dag`} className="btn btn-secondary" style={{ textDecoration: "none" }}>Edit DAG</Link>}
          {isEditable && <Link to={`/deals/${dealId}/export`} className="btn btn-secondary" style={{ textDecoration: "none" }}>Export builder</Link>}
          {isArchived && isModeler && <button className="btn btn-primary" onClick={handleReactivate}>Reactivate</button>}
          {(!isAnalyst || deal.status === "active") && <Link to="/processing" className="btn btn-primary" style={{ textDecoration: "none" }}>Process</Link>}
        </div>
      </div>

      {isArchived && (
        <div className="banner banner-warn" style={{ marginBottom: 16 }}>
          This deal is archived. All edits are locked.{isModeler ? " Reactivate to make changes." : ""}
        </div>
      )}

      <div className="tabs">
        {["overview", "info", "mappings", "tranches", "dag", "validations", "waterfall", "export", "runs"].map((t) => (
          <button key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t === "dag" ? "DAG" : t.charAt(0).toUpperCase() + t.slice(1)}
            {t === "mappings" && ` (${mappings.length})`}
            {t === "tranches" && ` (${tranches.length})`}
            {t === "dag" && dag && ` (${dag.nodes.filter((n) => n.node_type !== "validation").length})`}
            {t === "validations" && dag && ` (${dag.nodes.filter((n) => n.node_type === "validation").length})`}
            {t === "export" && ` (${exportTemplates.length} templates)`}
            {t === "runs" && ` (${runs.length})`}
          </button>
        ))}
      </div>

      {/* ── Overview Tab ── */}
      {tab === "overview" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div className="card">
            <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>VARIABLE MAPPINGS</div>
            <div style={{ fontSize: 28, fontWeight: 600 }}>{mappings.length}</div>
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 4 }}>cells mapped to variables</div>
          </div>
          <div className="card">
            <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>TRANCHES</div>
            <div style={{ fontSize: 28, fontWeight: 600 }}>{tranches.length}</div>
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 4 }}>
              Classes: {tranches.map((t) => t.class_label).join(", ") || "—"}
            </div>
          </div>
          <div className="card">
            <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}>DAG</div>
            <div style={{ fontSize: 28, fontWeight: 600 }}>{dag ? dag.nodes.length : 0}</div>
            <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 4 }}>
              {dag ? `v${dag.version.version_number} · ${dag.edges.length} edges` : "Not configured"}
            </div>
          </div>
        </div>
      )}

      {/* ── File output overrides (Overview tab) ── */}
      {tab === "overview" && deal && (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>File output directories</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
                Export directory override
              </label>
              <input
                className="input"
                value={(deal as any).export_directory_override ?? ""}
                disabled={isArchived}
                onChange={(e) => {
                  const next = e.target.value;
                  setDeal({ ...deal, export_directory_override: next } as Deal);
                }}
                onBlur={(e) => {
                  api.patch(`/deals/${deal.id}`, { export_directory_override: e.target.value || null });
                }}
                placeholder="Leave blank to use the global default"
                style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}
              />
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                CSV exports for this deal will be written under this path instead of the global export directory.
              </div>
            </div>
            <div>
              <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
                DAG archive directory override
              </label>
              <input
                className="input"
                value={(deal as any).dag_archive_directory_override ?? ""}
                disabled={isArchived}
                onChange={(e) => {
                  const next = e.target.value;
                  setDeal({ ...deal, dag_archive_directory_override: next } as Deal);
                }}
                onBlur={(e) => {
                  api.patch(`/deals/${deal.id}`, { dag_archive_directory_override: e.target.value || null });
                }}
                placeholder="Leave blank to use the global default"
                style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}
              />
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                Every saved DAG version is dumped as JSON to this path (for regulatory file archiving).
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Deal Info Tab ── */}
      {tab === "info" && deal && (
        <DealInfoTab
          deal={deal}
          onDealChanged={setDeal}
          readOnly={isArchived || isAnalyst}
        />
      )}

      {/* ── Mappings Tab ── */}
      {tab === "mappings" && (
        <div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 12 }}>
            <Link to={`/deals/${dealId}/mappings/cells`} className="btn btn-secondary">Open Cell Mapper</Link>
            {isEditable && (
              <button className="btn btn-primary" onClick={() => { setEditingMapping(null); setShowMappingDialog(true); }}>+ Add mapping</button>
            )}
          </div>
          {mappings.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📍</div>
              <div className="empty-state-title">No variable mappings</div>
              <div className="empty-state-text">Upload a servicer tape and map cells to variables.</div>
              {isModeler && (
                <button className="btn btn-primary" onClick={() => { setEditingMapping(null); setShowMappingDialog(true); }}>+ Add mapping</button>
              )}
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Canonical name</th><th>Display name</th><th>Sheet</th><th>Cell</th><th>Tape label</th>{isEditable && <th style={{ width: 100 }}>Actions</th>}</tr>
              </thead>
              <tbody>
                {mappings.map((m) => {
                  const alias = dealAliases[m.variable_id];
                  const isEditingAlias = editingAliasVarId === m.variable_id;
                  const displayName = alias || m.variable?.display_name || m.variable?.name || "—";
                  return (
                    <tr key={m.id}>
                      <td><code style={{ color: "var(--accent-green)", fontSize: 12 }}>{m.variable?.name || `var_${m.variable_id}`}</code></td>
                      <td>
                        {isEditingAlias ? (
                          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                            <input
                              className="input"
                              style={{ padding: "4px 8px", fontSize: 13, width: 180 }}
                              value={aliasInput}
                              onChange={(e) => setAliasInput(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && aliasInput.trim()) handleSaveAlias(m.variable_id, aliasInput);
                                if (e.key === "Escape") setEditingAliasVarId(null);
                              }}
                              autoFocus
                              placeholder="Display alias…"
                            />
                            <button className="btn btn-primary btn-sm" onClick={() => { if (aliasInput.trim()) handleSaveAlias(m.variable_id, aliasInput); }} disabled={!aliasInput.trim()}>Save</button>
                            {alias && <button className="btn btn-danger btn-sm" onClick={() => handleClearAlias(m.variable_id)}>Clear</button>}
                            <button className="btn btn-ghost btn-sm" onClick={() => setEditingAliasVarId(null)}>Cancel</button>
                          </div>
                        ) : (
                          <span
                            style={{ color: alias ? "var(--accent-purple)" : "var(--text-secondary)", cursor: isEditable ? "pointer" : "default", fontSize: 13 }}
                            onClick={() => { if (isEditable) { setEditingAliasVarId(m.variable_id); setAliasInput(alias ?? ""); } }}
                            title={isEditable ? "Click to set deal-specific display name" : undefined}
                          >
                            {displayName}
                            {isEditable && !alias && <span style={{ marginLeft: 4, fontSize: 11, color: "var(--accent-blue)" }}>+ set</span>}
                          </span>
                        )}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>{m.sheet_name}</td>
                      <td><code style={{ color: "var(--accent-blue)" }}>{m.column_letter}{m.row_number}</code></td>
                      <td>{m.tape_label ?? "—"}</td>
                      {isEditable && (
                        <td>
                          <div style={{ display: "flex", gap: 4 }}>
                            <button className="btn btn-ghost btn-sm" onClick={() => { setEditingMapping(m); setShowMappingDialog(true); }}>Edit</button>
                            <button className="btn btn-danger btn-sm" onClick={() => handleDeleteMapping(m)}>Delete</button>
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Tranches Tab ── */}
      {tab === "tranches" && (
        <div>
          {isEditable && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
              <button className="btn btn-primary" onClick={() => { setEditingTranche(null); setShowTrancheDialog(true); }}>+ Add tranche</button>
            </div>
          )}
          {tranches.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <div className="empty-state-title">No tranches configured</div>
              <div className="empty-state-text">Add note classes with their CUSIPs and rates.</div>
              {isEditable && (
                <button className="btn btn-primary" onClick={() => { setEditingTranche(null); setShowTrancheDialog(true); }}>+ Add tranche</button>
              )}
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 12 }}>
              {tranches.map((t) => (
                <div key={t.id} className="card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <span style={{ fontSize: 18, fontWeight: 600 }}>Class {t.class_label}</span>
                    <span className="badge badge-active">{t.regulation_type}</span>
                  </div>
                  {t.note_rate != null && (
                    <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 4 }}>
                      Rate: {(Number(t.note_rate) * 100).toFixed(2)}%
                    </div>
                  )}
                  {t.original_balance != null && (
                    <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                      Original: ${Number(t.original_balance).toLocaleString()}
                    </div>
                  )}
                  {t.cusip && (
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                      CUSIP: {t.cusip}
                    </div>
                  )}
                  {t.maturity_date && (
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                      Maturity: {t.maturity_date}
                    </div>
                  )}
                  {isEditable && (
                    <div style={{ display: "flex", gap: 6, marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => { setEditingTranche(t); setShowTrancheDialog(true); }}>Edit</button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDeleteTranche(t)}>Delete</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── DAG Tab (payment graph only — validations live on the Validations tab) ── */}
      {tab === "dag" && (
        <div>
          {!dag ? (
            <div className="empty-state">
              <div className="empty-state-icon">🔗</div>
              <div className="empty-state-title">No DAG configured</div>
              <div className="empty-state-text">Build a calculation graph with input, calculation, and distribution nodes.</div>
            </div>
          ) : (() => {
            const paymentNodes = dag.nodes.filter((n) => n.node_type !== "validation");
            return (
              <div>
                <div className="banner banner-info" style={{ marginBottom: 16 }}>
                  Version {dag.version.version_number} · {paymentNodes.length} payment nodes · {dag.edges.length} edges
                  · by {dag.version.created_by}
                  {dag.version.description && ` · "${dag.version.description}"`}
                </div>

                <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
                  {["input_value", "calculation", "distribution"].map((nt) => {
                    const count = paymentNodes.filter((n) => n.node_type === nt).length;
                    return (
                      <div key={nt} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                        <span style={{ width: 10, height: 10, borderRadius: "50%", background: nodeColor[nt], display: "inline-block" }} />
                        {nt.replace("_", " ")} ({count})
                      </div>
                    );
                  })}
                </div>

                <table className="table">
                  <thead>
                    <tr><th>#</th><th>Node</th><th>Type</th><th>Formula</th><th>Export</th></tr>
                  </thead>
                  <tbody>
                    {paymentNodes.map((n, i) => (
                      <tr key={n.id}>
                        <td style={{ color: "var(--text-muted)" }}>{i + 1}</td>
                        <td>
                          <span style={{ color: nodeColor[n.node_type], marginRight: 6, fontSize: 10 }}>●</span>
                          {n.name}
                        </td>
                        <td style={{ color: "var(--text-muted)", fontSize: 12 }}>{n.node_type.replace("_", " ")}</td>
                        <td><code style={{ fontSize: 12, color: "var(--text-secondary)" }}>{n.formula ?? "—"}</code></td>
                        <td>{n.export_field ? <code style={{ fontSize: 12, color: "var(--accent-purple)" }}>{n.export_field}</code> : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })()}
        </div>
      )}

      {/* ── Validations Tab ── */}
      {tab === "validations" && dag && (
        <ValidationsTab
          dag={dag}
          mappedVariables={variables.filter((v) =>
            new Set(mappings.map((m) => m.variable_id)).has(v.id),
          )}
          isEditable={isEditable}
          dealId={Number(dealId)}
          onRefreshDag={reloadDag}
        />
      )}

      {/* ── Waterfall Tab ── */}
      {tab === "waterfall" && deal && (
        <WaterfallTab
          deal={deal}
          isArchived={isArchived}
          isEditable={isEditable}
          runs={runs}
          dag={dag}
          mappedVariables={variables.filter((v) => new Set(mappings.map((m) => m.variable_id)).has(v.id))}
          onRefreshDag={reloadDag}
          onDealUpdate={(next) => setDeal({ ...deal, ...next } as Deal)}
        />
      )}

      {/* ── Export Tab ── */}
      {tab === "export" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div className="tabs" style={{ marginBottom: 0 }}>
              {exportTemplates.map((t) => (
                <button
                  key={t.id}
                  className={`tab ${activeExportTemplateId === t.id ? "active" : ""}`}
                  onClick={() => setActiveExportTemplateId(t.id)}
                >
                  {t.name}
                </button>
              ))}
            </div>
            {isEditable && (
              <Link to={`/deals/${dealId}/export`} className="btn btn-primary" style={{ textDecoration: "none" }}>
                Edit Mappings
              </Link>
            )}
          </div>
          {/* Template columns summary */}
          {exportTemplateColumns.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>
                COLUMNS: {exportTemplateColumns.map((c) => c.header_label).join(" | ")}
              </div>
            </div>
          )}

          {/* Deal export row config summary */}
          {exportDealRows.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-title">No export rows configured</div>
              <div className="empty-state-text">
                {isEditable
                  ? "Open the Export Config to define how each distribution maps to CSV rows."
                  : "An analytics team member will configure the export row routing."}
              </div>
            </div>
          ) : (
            (() => {
              // Group rows by node
              const byNode: Record<string, typeof exportDealRows> = {};
              for (const r of exportDealRows) {
                const key = r.node_name ?? r.node_key ?? `node_${r.node_id}`;
                (byNode[key] ??= []).push(r);
              }
              return (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Distribution Node</th>
                      <th>Export Rows</th>
                      <th>Cells Configured</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(byNode).map(([nodeName, rows]) => (
                      <tr key={nodeName}>
                        <td style={{ fontWeight: 500 }}>{nodeName}</td>
                        <td>{rows.length} row{rows.length !== 1 ? "s" : ""}</td>
                        <td style={{ color: "var(--text-muted)" }}>
                          {rows.reduce((sum, r) => sum + r.cells.length, 0)} cells
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()
          )}
        </div>
      )}

      {/* ── Runs Tab ── */}
      {tab === "runs" && (
        <div>
          {runs.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">⚙️</div>
              <div className="empty-state-title">No processing runs</div>
              <div className="empty-state-text">Go to Processing to upload a tape and run calculations.</div>
              <Link to="/processing" className="btn btn-primary" style={{ textDecoration: "none" }}>Start processing</Link>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Run ID</th><th>Period</th><th>Status</th><th>Distribution</th><th>Validations</th><th>By</th><th>Date</th></tr>
              </thead>
              <tbody>
                {runs.map((r: any) => (
                  <tr key={r.id}>
                    <td style={{ fontFamily: "monospace", color: "var(--accent-blue)" }}>RUN-{r.id}</td>
                    <td>{r.report_period}</td>
                    <td><span className={`badge badge-${r.status === "completed" ? "active" : r.status === "failed" ? "deal" : "draft"}`}>{r.status}</span></td>
                    <td style={{ fontFamily: "monospace" }}>{r.total_distribution ? `$${Number(r.total_distribution).toLocaleString()}` : "—"}</td>
                    <td>{r.validations_total != null ? <span style={{ color: r.validations_passed === r.validations_total ? "var(--accent-green)" : "var(--accent-red)" }}>{r.validations_passed}/{r.validations_total}</span> : "—"}</td>
                    <td style={{ color: "var(--text-muted)" }}>{r.created_by}</td>
                    <td style={{ color: "var(--text-muted)" }}>{new Date(r.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Clone Dialog ── */}
      {showClone && deal && <CloneDialog deal={deal} onClose={() => setShowClone(false)} onCloned={(id) => navigate(`/deals/${id}`)} />}

      {/* ── Mapping Dialog ── */}
      {showMappingDialog && (
        <MappingDialog
          dealId={Number(dealId)}
          mapping={editingMapping}
          existingMappings={mappings}
          onClose={() => { setShowMappingDialog(false); setEditingMapping(null); }}
          onSaved={() => { setShowMappingDialog(false); setEditingMapping(null); reloadMappings(); }}
        />
      )}

      {/* ── Tranche Dialog ── */}
      {showTrancheDialog && (
        <TrancheDialog
          dealId={Number(dealId)}
          tranche={editingTranche}
          onClose={() => { setShowTrancheDialog(false); setEditingTranche(null); }}
          onSaved={() => { setShowTrancheDialog(false); setEditingTranche(null); reloadTranches(); }}
        />
      )}

      {/* Live preview — stays docked across tabs so formula / waterfall /
          validation edits can be verified against a real tape without
          leaving the page. */}
      {deal && (
        <PreviewPanel
          dealId={deal.id}
          open={previewOpen}
          onToggle={() => setPreviewOpen((v) => !v)}
        />
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────── */
/*  Waterfall Tab                                                         */
/* ────────────────────────────────────────────────────────────────────── */

function WaterfallTab({
  deal,
  isArchived,
  isEditable,
  runs,
  dag,
  mappedVariables,
  onRefreshDag,
  onDealUpdate,
}: {
  deal: Deal;
  isArchived: boolean;
  isEditable: boolean;
  runs: any[];
  dag: DagData | null;
  mappedVariables: Variable[];
  onRefreshDag: () => void;
  onDealUpdate: (fields: Partial<Deal>) => void;
}) {
  const queryClient = useQueryClient();
  // Drag-and-drop state for waterfall reordering. Tracks which row is being
  // dragged and which row the cursor is hovering over (for the insertion hint).
  const [dragFromId, setDragFromId] = useState<number | null>(null);
  const [dragOverId, setDragOverId] = useState<number | null>(null);
  const viewableRuns = runs.filter((r) => r.status === "executed" || r.status === "completed");
  const [selectedRunId, setSelectedRunId] = useState<number | null>(
    viewableRuns.length > 0 ? viewableRuns[0].id : null,
  );

  // Distribution nodes ordered by waterfall_order, for the setup / structure preview.
  const distributionSteps = ((dag?.nodes ?? []) as any[])
    .filter((n) => n.node_type === "distribution")
    .sort((a, b) => {
      const ao = a.waterfall_order ?? 1e9;
      const bo = b.waterfall_order ?? 1e9;
      if (ao !== bo) return ao - bo;
      return (a.name || "").localeCompare(b.name || "");
    });

  // Calculation nodes — the permitted compare targets for waterfall
  // distributions. A distribution is a tape passthrough (what the servicer
  // reported it paid); the meaningful reconciliation is "paid vs. our
  // independent recalculation", so compare targets are calc nodes like
  // `svc_fee_calc`, `class_a_interest_calc`, etc.
  const calcNodes = ((dag?.nodes ?? []) as any[])
    .filter((n) => n.node_type === "calculation")
    .sort((a, b) => (a.name || "").localeCompare(b.name || ""));

  const patchNode = async (nodeId: number, fields: Record<string, unknown>) => {
    try {
      await api.patch(`/deals/${deal.id}/dag/nodes/${nodeId}`, fields);
      onRefreshDag();
      // Preview is hosted on DealDetailPage; live-refresh it on every edit.
      queryClient.invalidateQueries({ queryKey: ["preview", deal.id] });
    } catch (e) {
      console.error("Failed to update node", e);
    }
  };

  // Drag-and-drop: drop row N onto row M → reorder and renumber all rows 1..N.
  // Issues one PATCH per row in parallel, then refreshes.
  const handleWaterfallDrop = async (draggedId: number, targetId: number) => {
    if (draggedId === targetId) return;
    const ids = distributionSteps.map((s) => s.id);
    const fromIdx = ids.indexOf(draggedId);
    const toIdx = ids.indexOf(targetId);
    if (fromIdx < 0 || toIdx < 0) return;
    const reordered = [...ids];
    const [moved] = reordered.splice(fromIdx, 1);
    reordered.splice(toIdx, 0, moved);
    try {
      await Promise.all(
        reordered.map((nodeId, i) =>
          api.patch(`/deals/${deal.id}/dag/nodes/${nodeId}`, { waterfall_order: i + 1 }),
        ),
      );
      onRefreshDag();
      queryClient.invalidateQueries({ queryKey: ["preview", deal.id] });
    } catch (e) {
      console.error("Failed to reorder waterfall", e);
    }
  };

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Waterfall configuration</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div>
            <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Starting variable</label>
            <input
              className="input"
              value={(deal as any).waterfall_starting_var ?? "total_available_funds"}
              disabled={isArchived}
              onChange={(e) => {
                api.patch(`/deals/${deal.id}/waterfall-config`, { waterfall_starting_var: e.target.value });
                onDealUpdate({ waterfall_starting_var: e.target.value } as any);
              }}
              style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}
            />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Ending variable (reconciliation)</label>
            <input
              className="input"
              value={(deal as any).waterfall_ending_var ?? "end_available_funds"}
              disabled={isArchived}
              onChange={(e) => {
                api.patch(`/deals/${deal.id}/waterfall-config`, { waterfall_ending_var: e.target.value });
                onDealUpdate({ waterfall_ending_var: e.target.value } as any);
              }}
              style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}
            />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>Reconciliation tolerance</label>
            <input
              className="input"
              value={(deal as any).waterfall_tolerance ?? "0.01"}
              disabled={isArchived}
              onChange={(e) => {
                api.patch(`/deals/${deal.id}/waterfall-config`, { waterfall_tolerance: e.target.value });
                onDealUpdate({ waterfall_tolerance: e.target.value } as any);
              }}
              style={{ fontFamily: "var(--font-mono)", fontSize: 13, width: 120 }}
            />
          </div>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>
          The waterfall checks that the sum of all distributions starting from the starting variable equals the tape-reported ending variable.
        </div>
      </div>

      {/* Waterfall setup — editable order + compare target per distribution */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>Waterfall setup</div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 12 }}>
          Distribution amounts are tape passthroughs (what the servicer reported paying). The
          Waterfall UI automatically shows the running balance after each step, so formulas stay
          simple. For each row, pick a <em>calculation</em> node (e.g. <code>svc_fee_calc</code> or
          <code>class_a_interest_calc</code>) to compare against — the tape-paid amount is
          reconciled against our independent recalculation so waivers and off-contract payments
          surface clearly. <strong>Drag the <code>⋮⋮</code> handle to reorder.</strong>
        </div>
        {distributionSteps.length === 0 ? (
          <div style={{ color: "var(--text-muted)", fontSize: 13, fontStyle: "italic" }}>
            No distribution nodes configured. Add distribution nodes in the DAG editor to build the waterfall.
          </div>
        ) : (
          <>
            <div
              style={{
                padding: 10,
                background: "rgba(74,158,255,0.08)",
                border: "1px solid rgba(74,158,255,0.2)",
                borderRadius: "var(--radius)",
                marginBottom: 10,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Starting balance</div>
                <code style={{ fontSize: 13, color: "var(--accent-blue)" }}>
                  {(deal as any).waterfall_starting_var ?? "total_available_funds"}
                </code>
              </div>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 30 }}></th>
                  <th style={{ width: 40 }}>#</th>
                  <th>Distribution</th>
                  <th>Export field</th>
                  <th>Compare against</th>
                  <th>Formula</th>
                </tr>
              </thead>
              <tbody>
                {distributionSteps.map((s, idx) => (
                  <tr
                    key={s.id}
                    onDragOver={(e) => {
                      if (dragFromId !== null) {
                        e.preventDefault();
                        setDragOverId(s.id);
                      }
                    }}
                    onDragLeave={() => {
                      if (dragOverId === s.id) setDragOverId(null);
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (dragFromId !== null && dragFromId !== s.id) {
                        handleWaterfallDrop(dragFromId, s.id);
                      }
                      setDragFromId(null);
                      setDragOverId(null);
                    }}
                    style={{
                      background:
                        dragOverId === s.id && dragFromId !== s.id
                          ? "rgba(96,165,250,0.12)"
                          : dragFromId === s.id
                            ? "rgba(96,165,250,0.05)"
                            : undefined,
                      opacity: dragFromId === s.id ? 0.5 : 1,
                      transition: "background 0.1s",
                    }}
                  >
                    <td
                      draggable={isEditable}
                      onDragStart={() => {
                        setDragFromId(s.id);
                      }}
                      onDragEnd={() => {
                        setDragFromId(null);
                        setDragOverId(null);
                      }}
                      title={isEditable ? "Drag to reorder" : undefined}
                      style={{
                        color: "var(--text-muted)",
                        cursor: isEditable ? "grab" : "default",
                        userSelect: "none",
                        textAlign: "center",
                        fontSize: 14,
                        lineHeight: 1,
                      }}
                    >
                      ⋮⋮
                    </td>
                    <td style={{ color: "var(--text-muted)" }}>{idx + 1}</td>
                    <td style={{ fontWeight: 500 }}>{s.name}</td>
                    <td>
                      {(s.export_field || (s as any).payment_type) ? (
                        <code style={{ fontSize: 11, color: "var(--accent-purple)" }}>{s.export_field || (s as any).payment_type}</code>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                    <td>
                      {isEditable ? (
                        <select
                          value={(s as any).comparison_variable ?? ""}
                          onChange={(e) => {
                            patchNode(s.id, { comparison_variable: e.target.value || null });
                          }}
                          style={{
                            minWidth: 200,
                            padding: "2px 6px",
                            background: "var(--bg-tertiary)",
                            border: "1px solid var(--border)",
                            borderRadius: 4,
                            color: (s as any).comparison_variable ? "var(--accent-green)" : "var(--text-muted)",
                            fontSize: 11,
                            fontFamily: "monospace",
                          }}
                        >
                          <option value="">— none —</option>
                          {calcNodes.length === 0 && (
                            <option value="" disabled>
                              (no calculation nodes configured — add some in the DAG Builder)
                            </option>
                          )}
                          {calcNodes.map((n) => (
                            <option key={n.id} value={n.key}>
                              {n.name} ({n.key})
                            </option>
                          ))}
                        </select>
                      ) : (
                        <code style={{ fontSize: 11, color: (s as any).comparison_variable ? "var(--accent-green)" : "var(--text-muted)" }}>
                          {(s as any).comparison_variable ?? "—"}
                        </code>
                      )}
                    </td>
                    <td style={{ maxWidth: 360 }}>
                      <code
                        style={{
                          fontSize: 11,
                          color: "var(--text-secondary)",
                          fontFamily: "var(--font-mono)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          display: "block",
                        }}
                      >
                        {s.formula ?? "—"}
                      </code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div
              style={{
                padding: 10,
                background: "rgba(148,163,184,0.08)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                marginTop: 10,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Ending reconciliation variable</div>
              <code style={{ fontSize: 13, color: "var(--accent-blue)" }}>
                {(deal as any).waterfall_ending_var ?? "end_available_funds"}
              </code>
            </div>
          </>
        )}
      </div>

      {/* Trace — actual numbers from a completed run */}
      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
          <div style={{ fontWeight: 600 }}>Run trace:</div>
          <select
            className="select"
            value={selectedRunId ?? ""}
            onChange={(e) => setSelectedRunId(e.target.value ? Number(e.target.value) : null)}
            disabled={viewableRuns.length === 0}
            style={{ minWidth: 300 }}
          >
            <option value="">{viewableRuns.length === 0 ? "No completed runs" : "— pick a run —"}</option>
            {viewableRuns.map((r) => (
              <option key={r.id} value={r.id}>
                RUN-{r.id} · {r.report_period} · {r.status}
              </option>
            ))}
          </select>
        </div>

        {selectedRunId ? (
          <WaterfallTrace dealId={deal.id} runId={selectedRunId} />
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: 13, fontStyle: "italic" }}>
            Pick a completed run above to see actual calculated amounts and tape reconciliation.
          </div>
        )}
      </div>
    </div>
  );
}


/* ────────────────────────────────────────────────────────────────────── */
/*  Mapping Dialog                                                       */
/* ────────────────────────────────────────────────────────────────────── */

function MappingDialog({
  dealId,
  mapping,
  existingMappings,
  onClose,
  onSaved,
}: {
  dealId: number;
  mapping: Mapping | null;
  existingMappings: Mapping[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!mapping;
  const [variableId, setVariableId] = useState(mapping?.variable_id?.toString() ?? "");
  const [sheetName, setSheetName] = useState(mapping?.sheet_name ?? "");
  const [columnLetter, setColumnLetter] = useState(mapping?.column_letter ?? "");
  const [rowNumber, setRowNumber] = useState(mapping?.row_number?.toString() ?? "");
  const [tapeLabel, setTapeLabel] = useState(mapping?.tape_label ?? "");
  const [variables, setVariables] = useState<Variable[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Exclude variables already mapped on this deal so users can't duplicate.
  const mappedVarIds = new Set(existingMappings.map((m) => m.variable_id));
  const availableVariables = variables.filter((v) => !mappedVarIds.has(v.id));

  useEffect(() => {
    api.get<Variable[]>(`/variables/available/${dealId}`).then(setVariables).catch(() => {
      // Fallback to system variables
      api.get<Variable[]>("/variables/?scope=system").then(setVariables);
    });
  }, [dealId]);

  const handleSave = async () => {
    if (!isEdit && !variableId) { setError("Variable is required"); return; }
    if (!sheetName.trim()) { setError("Sheet name is required"); return; }
    if (!columnLetter.trim()) { setError("Column letter is required"); return; }
    if (!rowNumber || isNaN(Number(rowNumber))) { setError("Valid row number is required"); return; }

    setSaving(true);
    setError("");
    try {
      if (isEdit) {
        await api.patch(`/deals/${dealId}/mappings/${mapping!.id}`, {
          sheet_name: sheetName.trim(),
          column_letter: columnLetter.trim().toUpperCase(),
          row_number: Number(rowNumber),
          tape_label: tapeLabel.trim() || null,
        });
      } else {
        await api.post(`/deals/${dealId}/mappings`, {
          variable_id: Number(variableId),
          sheet_name: sheetName.trim(),
          column_letter: columnLetter.trim().toUpperCase(),
          row_number: Number(rowNumber),
          tape_label: tapeLabel.trim() || null,
        });
      }
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 480 }}>
        <div className="dialog-title">{isEdit ? "Edit mapping" : "Add mapping"}</div>

        {error && <div className="banner banner-warn" style={{ marginBottom: 16 }}>{error}</div>}

        {!isEdit && (
          <div className="form-field">
            <label className="form-label">Variable</label>
            <select className="select" value={variableId} onChange={(e) => setVariableId(e.target.value)}>
              <option value="">Select a variable…</option>
              {availableVariables.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.display_name || v.name} ({v.scope})
                </option>
              ))}
            </select>
            {availableVariables.length === 0 && (
              <div className="form-help" style={{ color: "var(--text-muted)" }}>
                All available variables are already mapped on this deal.
              </div>
            )}
          </div>
        )}

        <div className="form-field">
          <label className="form-label">Tape label</label>
          <input className="input" value={tapeLabel} onChange={(e) => setTapeLabel(e.target.value)} placeholder="e.g. Beginning Pool Balance" />
          <div className="form-help">Friendly label from the servicer tape</div>
        </div>

        <div className="form-field">
          <label className="form-label">Sheet name</label>
          <input className="input" value={sheetName} onChange={(e) => setSheetName(e.target.value)} placeholder="e.g. Sheet1" />
        </div>

        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Column letter</label>
            <input className="input" value={columnLetter} onChange={(e) => setColumnLetter(e.target.value)} placeholder="e.g. B" style={{ textTransform: "uppercase" }} />
          </div>
          <div className="form-field">
            <label className="form-label">Row number</label>
            <input className="input" type="number" value={rowNumber} onChange={(e) => setRowNumber(e.target.value)} placeholder="e.g. 5" min={1} />
          </div>
        </div>

        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : isEdit ? "Update" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────── */
/*  Tranche Dialog                                                       */
/* ────────────────────────────────────────────────────────────────────── */

function TrancheDialog({
  dealId,
  tranche,
  onClose,
  onSaved,
}: {
  dealId: number;
  tranche: Tranche | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!tranche;
  const [classLabel, setClassLabel] = useState(tranche?.class_label ?? "");
  const [cusip, setCusip] = useState(tranche?.cusip ?? "");
  const [regulationType, setRegulationType] = useState(tranche?.regulation_type ?? "combined");
  const [noteRate, setNoteRate] = useState(tranche?.note_rate != null ? String(Number(tranche.note_rate) * 100) : "");
  const [originalBalance, setOriginalBalance] = useState(tranche?.original_balance != null ? String(tranche.original_balance) : "");
  const [maturityDate, setMaturityDate] = useState(tranche?.maturity_date ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!classLabel.trim()) { setError("Class label is required"); return; }

    setSaving(true);
    setError("");
    try {
      const body: Record<string, unknown> = {
        class_label: classLabel.trim().toUpperCase(),
        cusip: cusip.trim() || null,
        note_rate: noteRate ? Number(noteRate) / 100 : null,
        original_balance: originalBalance ? Number(originalBalance) : null,
        maturity_date: maturityDate || null,
      };
      if (!isEdit) {
        body.regulation_type = regulationType;
      }

      if (isEdit) {
        await api.patch(`/deals/${dealId}/tranches/${tranche!.id}`, body);
      } else {
        await api.post(`/deals/${dealId}/tranches`, body);
      }
      onSaved();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 480 }}>
        <div className="dialog-title">{isEdit ? "Edit tranche" : "Add tranche"}</div>

        {error && <div className="banner banner-warn" style={{ marginBottom: 16 }}>{error}</div>}

        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Class label</label>
            <input className="input" value={classLabel} onChange={(e) => setClassLabel(e.target.value)} placeholder="e.g. A" style={{ textTransform: "uppercase" }} />
            <div className="form-help">Short label like A, B, M, etc.</div>
          </div>
          <div className="form-field">
            <label className="form-label">Regulation type</label>
            <select className="select" value={regulationType} onChange={(e) => setRegulationType(e.target.value)} disabled={isEdit}>
              <option value="combined">Combined</option>
              <option value="144a">144A</option>
              <option value="regs">Reg S</option>
            </select>
          </div>
        </div>

        <div className="form-field">
          <label className="form-label">CUSIP</label>
          <input className="input" value={cusip} onChange={(e) => setCusip(e.target.value)} placeholder="e.g. 00000AAA0" />
        </div>

        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Note rate (%)</label>
            <input className="input" type="number" step="0.01" value={noteRate} onChange={(e) => setNoteRate(e.target.value)} placeholder="e.g. 5.25" />
            <div className="form-help">Annual rate as percentage</div>
          </div>
          <div className="form-field">
            <label className="form-label">Original balance ($)</label>
            <input className="input" type="number" step="0.01" value={originalBalance} onChange={(e) => setOriginalBalance(e.target.value)} placeholder="e.g. 100000000" />
          </div>
        </div>

        <div className="form-field">
          <label className="form-label">Maturity date</label>
          <input className="input" type="date" value={maturityDate} onChange={(e) => setMaturityDate(e.target.value)} />
        </div>

        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : isEdit ? "Update" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────── */
/*  Clone Dialog                                                         */
/* ────────────────────────────────────────────────────────────────────── */

function CloneDialog({ deal, onClose, onCloned }: { deal: Deal; onClose: () => void; onCloned: (id: number) => void }) {
  const [name, setName] = useState(`${deal.name} (copy)`);
  const [cloneDag, setCloneDag] = useState(true);
  const [cloneMappings, setCloneMappings] = useState(true);
  const [cloneExports, setCloneExports] = useState(true);
  const [cloneTranches, setCloneTranches] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleClone = async () => {
    if (!name.trim()) { setError("Name is required"); return; }
    setSaving(true); setError("");
    try {
      const res = await api.post<{ id: number }>(`/deals/${deal.id}/clone`, {
        new_name: name.trim(), clone_dag: cloneDag, clone_mappings: cloneMappings,
        clone_exports: cloneExports, clone_tranches: cloneTranches,
      });
      onCloned(res.id);
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  };

  const Checkbox = ({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) => (
    <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", padding: "6px 0" }}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} style={{ accentColor: "var(--accent-blue)" }} />
      <span style={{ fontSize: 14 }}>{label}</span>
    </label>
  );

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 460 }}>
        <div className="dialog-title">Clone deal</div>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 16 }}>
          Create a new deal based on <strong>{deal.name}</strong>. All selected configurations will be copied.
        </div>

        {error && <div className="banner banner-warn" style={{ marginBottom: 16 }}>{error}</div>}

        <div className="card" style={{ padding: 12, marginBottom: 16, fontSize: 13 }}>
          <strong>{deal.name}</strong>
          <div style={{ color: "var(--text-muted)" }}>{deal.product_type} · {deal.status}</div>
        </div>

        <div className="form-field">
          <label className="form-label">New deal name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>

        <div style={{ marginBottom: 16 }}>
          <div className="form-label">What to clone</div>
          <Checkbox checked={cloneDag} onChange={setCloneDag} label="DAG structure (all nodes and edges)" />
          <Checkbox checked={cloneMappings} onChange={setCloneMappings} label="Variable mappings (sheet/row/col references)" />
          <Checkbox checked={cloneExports} onChange={setCloneExports} label="Export template configuration" />
          <Checkbox checked={cloneTranches} onChange={setCloneTranches} label="Tranches (class labels, rates, original balances)" />
        </div>

        <div className="form-help" style={{ marginBottom: 16 }}>
          The new deal will be created in Draft status. Variable mappings may need adjustment if the servicer tape layout differs.
        </div>

        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleClone} disabled={saving}>{saving ? "Cloning..." : "Clone deal"}</button>
        </div>
      </div>
    </div>
  );
}
