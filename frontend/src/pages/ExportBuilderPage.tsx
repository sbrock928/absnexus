import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/auth";
import { useToast } from "@/components/Toast";
import { api } from "@/api/client";
import type { Deal } from "@/types";
import { fetchNodes, type DagNode } from "@/api/dag";
import {
  listTemplates,
  getTemplate,
  getDealMappings,
  saveDealMappings,
} from "@/api/globalExport";

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

  // Load templates
  const { data: templates = [] } = useQuery({
    queryKey: ["global-templates"],
    queryFn: listTemplates,
  });

  const activeTemplateId = selectedTemplateId ?? templates[0]?.id ?? null;

  // Load template columns
  const { data: templateData } = useQuery({
    queryKey: ["global-template", activeTemplateId],
    queryFn: () => getTemplate(activeTemplateId!),
    enabled: activeTemplateId !== null,
  });

  const columns = templateData?.columns ?? [];
  // Load deal's distribution nodes
  const { data: allNodes = [] } = useQuery({
    queryKey: ["dag-nodes", id],
    queryFn: () => fetchNodes(id),
  });
  const distNodes = allNodes.filter((n: DagNode) => n.node_type === "distribution");

  // Load existing mappings
  const { data: existingMappings = [] } = useQuery({
    queryKey: ["deal-export-mappings", id, activeTemplateId],
    queryFn: () => getDealMappings(id, activeTemplateId!),
    enabled: activeTemplateId !== null,
  });

  // Local mapping state: column_id → node_id
  const [localMappings, setLocalMappings] = useState<Record<number, number>>({});
  const [initialized, setInitialized] = useState(false);

  // Initialize from server mappings when they load
  if (existingMappings.length > 0 && !initialized) {
    const map: Record<number, number> = {};
    for (const m of existingMappings) {
      map[m.column_id] = m.node_id;
    }
    setLocalMappings(map);
    setInitialized(true);
  }

  // Reset when template changes
  const handleTemplateChange = (tid: number) => {
    setSelectedTemplateId(tid);
    setLocalMappings({});
    setInitialized(false);
  };

  const saveMut = useMutation({
    mutationFn: () => {
      const mappings = Object.entries(localMappings)
        .filter(([, nodeId]) => nodeId > 0)
        .map(([colId, nodeId]) => ({ column_id: Number(colId), node_id: nodeId }));
      return saveDealMappings(id, activeTemplateId!, mappings);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deal-export-mappings", id, activeTemplateId] });
      toast("Export mappings saved");
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
        <Link to={`/deals/${dealId}`} style={{ color: "var(--accent-blue)", textDecoration: "none" }}>
          Deal
        </Link>
        {" / "}Export mappings
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Export Mappings</div>
          <div className="page-subtitle">
            Map distribution nodes to global template columns for {deal?.name ?? "this deal"}
          </div>
        </div>
        {isEditable && (
          <button
            className="btn btn-primary"
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending}
          >
            {saveMut.isPending ? "Saving..." : "Save mappings"}
          </button>
        )}
      </div>

      {isArchived && (
        <div className="banner banner-warn" style={{ marginBottom: 16 }}>
          Deal is archived. Mappings are read-only.
        </div>
      )}

      {/* Template tabs */}
      <div className="tabs">
        {templates.map((t) => (
          <button
            key={t.id}
            className={`tab ${activeTemplateId === t.id ? "active" : ""}`}
            onClick={() => handleTemplateChange(t.id)}
          >
            {t.name}
          </button>
        ))}
      </div>

      {activeTemplateId && columns.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>#</th>
              <th>Column Header</th>
              <th>Type</th>
              <th>Value / Mapping</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col, idx) => (
              <tr key={col.id}>
                <td style={{ color: "var(--text-muted)" }}>{idx + 1}</td>
                <td style={{ fontFamily: "monospace", fontWeight: 500 }}>{col.header_label}</td>
                <td>
                  <span className={`badge ${col.value_type === "distribution_node" ? "badge-active" : "badge-system"}`}>
                    {col.value_type}
                  </span>
                </td>
                <td>
                  {col.value_type === "distribution_node" ? (
                    <select
                      className="select"
                      style={{ width: 260, fontSize: 12 }}
                      value={localMappings[col.id] ?? ""}
                      disabled={!isEditable}
                      onChange={(e) => {
                        setLocalMappings((prev) => ({
                          ...prev,
                          [col.id]: Number(e.target.value),
                        }));
                      }}
                    >
                      <option value="">— Select node —</option>
                      {distNodes.map((n: DagNode) => (
                        <option key={n.id} value={n.id}>
                          {n.name} ({n.key})
                        </option>
                      ))}
                    </select>
                  ) : col.value_type === "literal" ? (
                    <code style={{ fontSize: 12, color: "var(--text-secondary)" }}>{col.literal_value}</code>
                  ) : (
                    <code style={{ fontSize: 12, color: "var(--text-secondary)" }}>{col.meta_field}</code>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {activeTemplateId && columns.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-title">No columns in this template</div>
          <div className="empty-state-text">
            An admin needs to configure columns on the{" "}
            <Link to="/export-templates" style={{ color: "var(--accent-blue)" }}>Export Templates</Link> page.
          </div>
        </div>
      )}
    </div>
  );
}
