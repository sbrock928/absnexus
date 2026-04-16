import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/auth";
import { useToast } from "@/components/Toast";
import { api } from "@/api/client";
import type { Deal, Variable } from "@/types";
import { fetchNodes, type DagNode } from "@/api/dag";
import {
  listTemplates,
  getTemplate,
  getDealExportConfig,
  saveDealExportConfig,
  type DealExportRowSave,
  type DealExportCellSave,
} from "@/api/globalExport";

const VALUE_SOURCES = [
  { value: "node", label: "DAG Node" },
  { value: "variable", label: "Tape Variable" },
  { value: "run_meta", label: "Run Meta" },
  { value: "deal_meta", label: "Deal Meta" },
];

const RUN_META_OPTIONS = [
  { value: "run_code", label: "Run Code" },
  { value: "payment_date", label: "Payment Date" },
  { value: "report_period", label: "Report Period" },
];

const DEAL_META_OPTIONS = [
  { value: "deal_id", label: "Deal ID" },
  { value: "deal_name", label: "Deal Name" },
  { value: "product_type", label: "Product Type" },
];

export function ExportBuilderPage() {
  const { dealId } = useParams<{ dealId: string }>();
  const id = Number(dealId);
  const { isModeler } = useAuth();
  const { toast } = useToast();
  const qc = useQueryClient();

  const { data: deal } = useQuery({
    queryKey: ["deal", id],
    queryFn: () => api.get<Deal>(`/deals/${id}`),
  });
  const isArchived = deal?.status === "archived";
  const isEditable = isModeler && !isArchived;

  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);

  const { data: templates = [] } = useQuery({
    queryKey: ["global-templates"],
    queryFn: listTemplates,
  });

  const activeTemplateId = selectedTemplateId ?? templates[0]?.id ?? null;

  const { data: templateData } = useQuery({
    queryKey: ["global-template", activeTemplateId],
    queryFn: () => getTemplate(activeTemplateId!),
    enabled: activeTemplateId !== null,
  });
  const columns = templateData?.columns ?? [];

  const { data: allNodes = [] } = useQuery({
    queryKey: ["dag-nodes", id],
    queryFn: () => fetchNodes(id),
  });
  const distNodes = allNodes.filter((n: DagNode) => n.node_type === "distribution");

  const { data: variables = [] } = useQuery({
    queryKey: ["variables-all"],
    queryFn: () => api.get<Variable[]>("/variables/"),
  });

  const { data: existingConfig } = useQuery({
    queryKey: ["deal-export-config", id, activeTemplateId],
    queryFn: () => getDealExportConfig(id, activeTemplateId!),
    enabled: activeTemplateId !== null,
  });

  // Local editable state: array of row configs
  interface LocalRow {
    key: string; // temp key for react
    node_id: number;
    row_order: number;
    identifier_group: number | null;
    cells: Record<number, { value_source: string; source_ref: string }>; // column_id → cell
  }

  const [localRows, setLocalRows] = useState<LocalRow[]>([]);

  // Sync from server config
  useEffect(() => {
    if (!existingConfig) { setLocalRows([]); return; }
    const rows: LocalRow[] = existingConfig.rows.map((r) => ({
      key: `server-${r.id}`,
      node_id: r.node_id,
      row_order: r.row_order,
      identifier_group: r.identifier_group,
      cells: Object.fromEntries(
        r.cells.map((c) => [c.column_id, { value_source: c.value_source, source_ref: c.source_ref }]),
      ),
    }));
    setLocalRows(rows);
  }, [existingConfig]);

  // Reset when template changes
  const handleTemplateChange = (tid: number) => {
    setSelectedTemplateId(tid);
    setLocalRows([]);
  };

  let nextKey = 0;
  const addRow = (nodeId: number) => {
    const existingForNode = localRows.filter((r) => r.node_id === nodeId);
    setLocalRows((prev) => [
      ...prev,
      {
        key: `new-${++nextKey}-${Date.now()}`,
        node_id: nodeId,
        row_order: existingForNode.length + 1,
        identifier_group: null,
        cells: {},
      },
    ]);
  };

  const removeRow = (key: string) => {
    setLocalRows((prev) => prev.filter((r) => r.key !== key));
  };

  const updateCell = (rowKey: string, columnId: number, field: "value_source" | "source_ref", value: string) => {
    setLocalRows((prev) =>
      prev.map((r) => {
        if (r.key !== rowKey) return r;
        const existing = r.cells[columnId] ?? { value_source: "literal", source_ref: "" };
        return {
          ...r,
          cells: { ...r.cells, [columnId]: { ...existing, [field]: value } },
        };
      }),
    );
  };

  const updateRowField = (rowKey: string, field: string, value: number | null) => {
    setLocalRows((prev) =>
      prev.map((r) => (r.key === rowKey ? { ...r, [field]: value } : r)),
    );
  };

  const saveMut = useMutation({
    mutationFn: () => {
      const payload: DealExportRowSave[] = localRows.map((r, idx) => ({
        node_id: r.node_id,
        row_order: idx + 1,
        identifier_group: r.identifier_group,
        cells: Object.entries(r.cells)
          .filter(([, c]) => c.source_ref)
          .map(([colId, c]): DealExportCellSave => ({
            column_id: Number(colId),
            value_source: c.value_source,
            source_ref: c.source_ref,
          })),
      }));
      return saveDealExportConfig(id, activeTemplateId!, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deal-export-config", id, activeTemplateId] });
      toast("Export config saved");
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  // Group local rows by distribution node
  const rowsByNode: Record<number, LocalRow[]> = {};
  for (const r of localRows) {
    (rowsByNode[r.node_id] ??= []).push(r);
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
        <Link to={`/deals/${dealId}`} style={{ color: "var(--accent-blue)", textDecoration: "none" }}>Deal</Link>
        {" / "}Export Config
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Export Row Config</div>
          <div className="page-subtitle">
            Configure how each distribution expands into CSV rows for {deal?.name ?? "this deal"}
          </div>
        </div>
        {isEditable && (
          <button className="btn btn-primary" onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
            {saveMut.isPending ? "Saving..." : "Save config"}
          </button>
        )}
      </div>

      {isArchived && (
        <div className="banner banner-warn" style={{ marginBottom: 16 }}>Deal is archived. Config is read-only.</div>
      )}

      <div className="tabs">
        {templates.map((t) => (
          <button key={t.id} className={`tab ${activeTemplateId === t.id ? "active" : ""}`} onClick={() => handleTemplateChange(t.id)}>
            {t.name}
          </button>
        ))}
      </div>

      {/* Per-distribution-node sections */}
      {distNodes.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No distribution nodes</div>
          <div className="empty-state-text">Configure distribution nodes in the DAG editor first.</div>
        </div>
      ) : (
        distNodes.map((node: DagNode) => {
          const nodeRows = rowsByNode[node.id] ?? [];
          return (
            <div key={node.id} className="card" style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <div>
                  <span style={{ fontWeight: 600 }}>{node.name}</span>
                  <code style={{ marginLeft: 8, fontSize: 11, color: "var(--text-muted)" }}>{node.key}</code>
                  <span className="badge badge-active" style={{ marginLeft: 8 }}>{nodeRows.length} rows</span>
                </div>
                {isEditable && (
                  <button className="btn btn-sm" onClick={() => addRow(node.id)}>+ Add row</button>
                )}
              </div>

              {nodeRows.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: 13, fontStyle: "italic" }}>
                  No export rows configured. Click "+ Add row" to define how this distribution appears in the CSV.
                </div>
              ) : (
                <table className="table" style={{ fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={{ width: 30 }}>#</th>
                      <th style={{ width: 50 }}>ID Grp</th>
                      {columns.map((col) => (
                        <th key={col.id} style={{ fontSize: 10 }}>{col.header_label}</th>
                      ))}
                      {isEditable && <th style={{ width: 40 }}></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {nodeRows.map((row, rowIdx) => (
                      <tr key={row.key}>
                        <td style={{ color: "var(--text-muted)" }}>{rowIdx + 1}</td>
                        <td>
                          <input
                            type="number"
                            value={row.identifier_group ?? ""}
                            disabled={!isEditable}
                            onChange={(e) => updateRowField(row.key, "identifier_group", e.target.value ? Number(e.target.value) : null)}
                            style={{ width: 40, padding: "2px 4px", background: "var(--bg-tertiary)", border: "1px solid var(--border)", borderRadius: 3, color: "var(--text-primary)", fontSize: 11 }}
                          />
                        </td>
                        {columns.map((col) => {
                          const cell = row.cells[col.id] ?? { value_source: "literal", source_ref: "" };
                          return (
                            <td key={col.id}>
                              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                                <select
                                  value={cell.value_source}
                                  disabled={!isEditable}
                                  onChange={(e) => { updateCell(row.key, col.id, "value_source", e.target.value); updateCell(row.key, col.id, "source_ref", ""); }}
                                  style={{ fontSize: 10, padding: "1px 2px", background: "var(--bg-tertiary)", border: "1px solid var(--border)", borderRadius: 2, color: "var(--text-primary)" }}
                                >
                                  {VALUE_SOURCES.map((vs) => (
                                    <option key={vs.value} value={vs.value}>{vs.label}</option>
                                  ))}
                                </select>
                                {cell.value_source === "node" && (
                                  <select
                                    value={cell.source_ref}
                                    disabled={!isEditable}
                                    onChange={(e) => updateCell(row.key, col.id, "source_ref", e.target.value)}
                                    style={{ fontSize: 10, padding: "1px 2px", background: "var(--bg-tertiary)", border: "1px solid var(--border)", borderRadius: 2, color: "var(--accent-blue)" }}
                                  >
                                    <option value="">— select node —</option>
                                    {allNodes.map((n: DagNode) => (
                                      <option key={n.id} value={n.key}>{n.name} ({n.key})</option>
                                    ))}
                                  </select>
                                )}
                                {cell.value_source === "variable" && (
                                  <select
                                    value={cell.source_ref}
                                    disabled={!isEditable}
                                    onChange={(e) => updateCell(row.key, col.id, "source_ref", e.target.value)}
                                    style={{ fontSize: 10, padding: "1px 2px", background: "var(--bg-tertiary)", border: "1px solid var(--border)", borderRadius: 2, color: "var(--accent-green)" }}
                                  >
                                    <option value="">— select variable —</option>
                                    {variables.map((v) => (
                                      <option key={v.id} value={v.name}>{v.display_name || v.name}</option>
                                    ))}
                                  </select>
                                )}
                                {cell.value_source === "run_meta" && (
                                  <select
                                    value={cell.source_ref}
                                    disabled={!isEditable}
                                    onChange={(e) => updateCell(row.key, col.id, "source_ref", e.target.value)}
                                    style={{ fontSize: 10, padding: "1px 2px", background: "var(--bg-tertiary)", border: "1px solid var(--border)", borderRadius: 2, color: "var(--text-secondary)" }}
                                  >
                                    <option value="">— select —</option>
                                    {RUN_META_OPTIONS.map((o) => (
                                      <option key={o.value} value={o.value}>{o.label}</option>
                                    ))}
                                  </select>
                                )}
                                {cell.value_source === "deal_meta" && (
                                  <select
                                    value={cell.source_ref}
                                    disabled={!isEditable}
                                    onChange={(e) => updateCell(row.key, col.id, "source_ref", e.target.value)}
                                    style={{ fontSize: 10, padding: "1px 2px", background: "var(--bg-tertiary)", border: "1px solid var(--border)", borderRadius: 2, color: "var(--text-secondary)" }}
                                  >
                                    <option value="">— select —</option>
                                    {DEAL_META_OPTIONS.map((o) => (
                                      <option key={o.value} value={o.value}>{o.label}</option>
                                    ))}
                                  </select>
                                )}
                              </div>
                            </td>
                          );
                        })}
                        {isEditable && (
                          <td>
                            <button
                              className="btn btn-ghost btn-sm"
                              style={{ color: "var(--accent-red)", fontSize: 10 }}
                              onClick={() => removeRow(row.key)}
                            >
                              Del
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
