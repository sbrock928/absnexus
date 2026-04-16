import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/auth";
import { api } from "@/api/client";
import type { Deal } from "@/types";
import { fetchNodes, type DagNode } from "@/api/dag";
import {
  listColumns,
  createColumn,
  updateColumn,
  deleteColumn,
  reorderColumns,
  copyPreset,
  listPresets,
  previewExport,
  type ExportColumn,
} from "@/api/export";
import styles from "./ExportBuilderPage.module.css";

const VALUE_TYPE_OPTIONS = [
  { value: "distribution_node", label: "Distribution node" },
  { value: "literal", label: "Literal value" },
  { value: "run_meta", label: "Run metadata" },
  { value: "deal_meta", label: "Deal metadata" },
];

const FORMAT_OPTIONS = [
  { value: "text", label: "Text" },
  { value: "decimal", label: "Decimal" },
  { value: "integer", label: "Integer" },
];

const RUN_META_OPTIONS = [
  { value: "run_code", label: "Run code" },
  { value: "payment_date", label: "Payment date" },
  { value: "report_period", label: "Report period" },
];

const DEAL_META_OPTIONS = [
  { value: "deal_id", label: "Deal ID" },
  { value: "deal_name", label: "Deal name" },
  { value: "product_type", label: "Product type" },
];

export function ExportBuilderPage() {
  const { dealId } = useParams<{ dealId: string }>();
  const id = Number(dealId);
  const { isModeler } = useAuth();
  const qc = useQueryClient();

  const { data: deal } = useQuery({
    queryKey: ["deal", id],
    queryFn: () => api.get<Deal>(`/deals/${id}`),
  });
  const isArchived = deal?.status === "archived";
  const isEditable = isModeler && !isArchived;

  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<ExportColumn | null>(null);
  const [showPresets, setShowPresets] = useState(false);

  const { data: columns = [] } = useQuery({
    queryKey: ["export-columns", id],
    queryFn: () => listColumns(id),
  });

  const { data: nodes = [] } = useQuery({
    queryKey: ["dag-nodes", id],
    queryFn: () => fetchNodes(id),
  });

  const { data: presets = [] } = useQuery({
    queryKey: ["presets"],
    queryFn: listPresets,
  });

  const { data: preview } = useQuery({
    queryKey: ["export-preview", id, columns.length],
    queryFn: () => previewExport(id),
  });

  const distributionNodes = nodes.filter(
    (n) => n.node_type === "distribution" && n.is_active,
  );

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["export-columns", id] });
    qc.invalidateQueries({ queryKey: ["export-preview", id] });
  };

  const createMut = useMutation({
    mutationFn: (payload: Partial<ExportColumn>) => createColumn(id, payload),
    onSuccess: () => {
      invalidate();
      setShowAdd(false);
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ cid, fields }: { cid: number; fields: Partial<ExportColumn> }) =>
      updateColumn(cid, fields),
    onSuccess: () => {
      invalidate();
      setEditing(null);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (cid: number) => deleteColumn(cid),
    onSuccess: invalidate,
  });

  const reorderMut = useMutation({
    mutationFn: (orderedIds: number[]) => reorderColumns(id, orderedIds),
    onSuccess: invalidate,
  });

  const presetMut = useMutation({
    mutationFn: (key: string) => copyPreset(id, key),
    onSuccess: () => {
      invalidate();
      setShowPresets(false);
    },
  });

  const moveUp = (idx: number) => {
    if (idx === 0) return;
    const ids = columns.map((c) => c.id);
    [ids[idx - 1], ids[idx]] = [ids[idx], ids[idx - 1]];
    reorderMut.mutate(ids);
  };

  const moveDown = (idx: number) => {
    if (idx === columns.length - 1) return;
    const ids = columns.map((c) => c.id);
    [ids[idx], ids[idx + 1]] = [ids[idx + 1], ids[idx]];
    reorderMut.mutate(ids);
  };

  const describeSource = (c: ExportColumn): string => {
    if (c.value_type === "distribution_node") {
      const node = nodes.find((n) => n.id === c.node_id);
      return `node: ${node?.key ?? "—"}${c.prorate_by ? ` (${c.prorate_by})` : ""}`;
    }
    if (c.value_type === "literal") return `literal: ${c.literal_value ?? ""}`;
    if (c.value_type === "run_meta") return `run: ${c.meta_field ?? ""}`;
    if (c.value_type === "deal_meta") return `deal: ${c.meta_field ?? ""}`;
    return "";
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Export builder</div>
          <div className="page-subtitle">
            {columns.length} column{columns.length !== 1 ? "s" : ""} configured
          </div>
        </div>
        {isEditable && (
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={() => setShowPresets(true)}>
              Copy from preset
            </button>
            <button className="btn btn-primary" onClick={() => setShowAdd(true)}>
              + Column
            </button>
          </div>
        )}
      </div>

      {/* Column list */}
      {columns.length === 0 ? (
        <div className={styles.emptyState}>
          No columns configured. Click &quot;Copy from preset&quot; to start from a
          standard format, or &quot;+ Column&quot; to build from scratch.
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>#</th>
              <th>Header</th>
              <th>Value source</th>
              <th>Format</th>
              {isEditable && <th style={{ width: 140 }}></th>}
            </tr>
          </thead>
          <tbody>
            {columns.map((c, idx) => (
              <tr key={c.id}>
                <td style={{ color: "var(--text-muted)" }}>{idx + 1}</td>
                <td style={{ fontFamily: "var(--font-mono)", fontWeight: 500 }}>
                  {c.header_label}
                </td>
                <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                  {describeSource(c)}
                </td>
                <td style={{ fontSize: 12 }}>
                  {c.format_type}
                  {c.format_type === "decimal" && c.decimal_places !== null && (
                    <span style={{ color: "var(--text-muted)" }}>
                      {" "}
                      ({c.decimal_places} pl)
                    </span>
                  )}
                </td>
                {isEditable && (
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button
                        className={styles.iconBtn}
                        onClick={() => moveUp(idx)}
                        disabled={idx === 0}
                      >
                        ↑
                      </button>
                      <button
                        className={styles.iconBtn}
                        onClick={() => moveDown(idx)}
                        disabled={idx === columns.length - 1}
                      >
                        ↓
                      </button>
                      <button
                        className={styles.actionLink}
                        onClick={() => setEditing(c)}
                      >
                        Edit
                      </button>
                      <button
                        className={styles.actionLink}
                        style={{ color: "var(--accent-red)" }}
                        onClick={() => {
                          if (window.confirm(`Delete column "${c.header_label}"?`)) {
                            deleteMut.mutate(c.id);
                          }
                        }}
                      >
                        Del
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Preview */}
      {columns.length > 0 && (
        <>
          <h3 className={styles.previewTitle}>Live preview</h3>
          <div className={styles.previewBox}>
            <pre>{preview?.csv ?? "Loading..."}</pre>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
            Placeholder values — actual run values will populate on export.
          </div>
        </>
      )}

      {/* Add/Edit Dialog */}
      {(showAdd || editing) && (
        <ColumnDialog
          column={editing}
          distributionNodes={distributionNodes}
          onSave={(payload) => {
            if (editing) {
              updateMut.mutate({ cid: editing.id, fields: payload });
            } else {
              createMut.mutate(payload);
            }
          }}
          onCancel={() => {
            setShowAdd(false);
            setEditing(null);
          }}
          isPending={createMut.isPending || updateMut.isPending}
        />
      )}

      {/* Preset Dialog */}
      {showPresets && (
        <PresetDialog
          presets={presets}
          onCopy={(key) => presetMut.mutate(key)}
          onCancel={() => setShowPresets(false)}
          hasExistingColumns={columns.length > 0}
          isPending={presetMut.isPending}
        />
      )}
    </div>
  );
}

// ── Column Dialog Component ──────────────────────────────────

interface ColumnDialogProps {
  column: ExportColumn | null;
  distributionNodes: DagNode[];
  onSave: (payload: Partial<ExportColumn>) => void;
  onCancel: () => void;
  isPending: boolean;
}

function ColumnDialog({
  column,
  distributionNodes,
  onSave,
  onCancel,
  isPending,
}: ColumnDialogProps) {
  const [header, setHeader] = useState(column?.header_label ?? "");
  const [valueType, setValueType] = useState(column?.value_type ?? "distribution_node");
  const [nodeId, setNodeId] = useState<number | null>(column?.node_id ?? null);
  const [literal, setLiteral] = useState(column?.literal_value ?? "");
  const [metaField, setMetaField] = useState(column?.meta_field ?? "");
  const [formatType, setFormatType] = useState(column?.format_type ?? "text");
  const [decimalPlaces, setDecimalPlaces] = useState(column?.decimal_places ?? 2);
  const [prorateBy, setProrateBy] = useState(column?.prorate_by ?? "");
  const [prorateClass, setProrateClass] = useState(column?.prorate_class_label ?? "");

  const handleSave = () => {
    if (!header) return;
    const payload: Partial<ExportColumn> = {
      header_label: header,
      value_type: valueType as ExportColumn["value_type"],
      format_type: formatType,
    };
    if (valueType === "distribution_node") {
      payload.node_id = nodeId;
      payload.decimal_places = decimalPlaces;
      if (prorateBy) payload.prorate_by = prorateBy;
      if (prorateClass) payload.prorate_class_label = prorateClass;
    } else if (valueType === "literal") {
      payload.literal_value = literal;
    } else {
      payload.meta_field = metaField;
    }
    onSave(payload);
  };

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.dialogTitle}>
          {column ? "Edit column" : "Add column"}
        </h2>

        <div className="form-group">
          <label className="form-label">Header label</label>
          <input
            className="input"
            value={header}
            onChange={(e) => setHeader(e.target.value)}
            placeholder="e.g. AMOUNT"
            style={{ fontFamily: "var(--font-mono)" }}
            autoFocus
          />
        </div>

        <div className="form-group">
          <label className="form-label">Value source</label>
          {VALUE_TYPE_OPTIONS.map((opt) => (
            <label key={opt.value} className={styles.radioLabel}>
              <input
                type="radio"
                name="valueType"
                value={opt.value}
                checked={valueType === opt.value}
                onChange={() => setValueType(opt.value)}
              />
              {opt.label}
            </label>
          ))}
        </div>

        {/* Distribution node dropdown */}
        {valueType === "distribution_node" && (
          <>
            <div className="form-group">
              <label className="form-label">Distribution node</label>
              <select
                className="select"
                style={{ width: "100%" }}
                value={nodeId ?? ""}
                onChange={(e) =>
                  setNodeId(e.target.value ? Number(e.target.value) : null)
                }
              >
                <option value="">— Select —</option>
                {distributionNodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.name} ({n.key})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Prorate (optional)</label>
              <select
                className="select"
                style={{ width: "100%" }}
                value={prorateBy}
                onChange={(e) => setProrateBy(e.target.value)}
              >
                <option value="">No prorate — use full amount</option>
                <option value="144a">144A portion only</option>
                <option value="regs">RegS portion only</option>
              </select>
              {prorateBy && (
                <input
                  className="input"
                  value={prorateClass}
                  onChange={(e) => setProrateClass(e.target.value.toUpperCase())}
                  placeholder="Class label (e.g. A)"
                  style={{ fontFamily: "var(--font-mono)", marginTop: 6 }}
                />
              )}
            </div>
          </>
        )}

        {/* Literal input */}
        {valueType === "literal" && (
          <div className="form-group">
            <label className="form-label">Literal value</label>
            <input
              className="input"
              value={literal}
              onChange={(e) => setLiteral(e.target.value)}
              placeholder="e.g. INTEREST"
            />
          </div>
        )}

        {/* Meta field selector */}
        {valueType === "run_meta" && (
          <div className="form-group">
            <label className="form-label">Run metadata field</label>
            <select
              className="select"
              style={{ width: "100%" }}
              value={metaField}
              onChange={(e) => setMetaField(e.target.value)}
            >
              <option value="">— Select —</option>
              {RUN_META_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {valueType === "deal_meta" && (
          <div className="form-group">
            <label className="form-label">Deal metadata field</label>
            <select
              className="select"
              style={{ width: "100%" }}
              value={metaField}
              onChange={(e) => setMetaField(e.target.value)}
            >
              <option value="">— Select —</option>
              {DEAL_META_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Format */}
        <div className="form-group">
          <label className="form-label">Format</label>
          <select
            className="select"
            style={{ width: "100%" }}
            value={formatType}
            onChange={(e) => setFormatType(e.target.value)}
          >
            {FORMAT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {formatType === "decimal" && (
            <input
              className="input"
              type="number"
              value={decimalPlaces}
              onChange={(e) => setDecimalPlaces(Number(e.target.value))}
              min={0}
              max={6}
              style={{ marginTop: 6, width: 120 }}
            />
          )}
        </div>

        <div className={styles.dialogActions}>
          <button className="btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={!header || isPending}
          >
            {isPending
              ? "Saving..."
              : column
                ? "Save changes"
                : "Add column"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Preset Dialog Component ──────────────────────────────────

interface PresetDialogProps {
  presets: Array<{
    key: string;
    name: string;
    description: string;
    column_count: number;
  }>;
  onCopy: (key: string) => void;
  onCancel: () => void;
  hasExistingColumns: boolean;
  isPending: boolean;
}

function PresetDialog({
  presets,
  onCopy,
  onCancel,
  hasExistingColumns,
  isPending,
}: PresetDialogProps) {
  const [selected, setSelected] = useState(presets[0]?.key ?? "");

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.dialogTitle}>Copy from preset</h2>
        <p style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
          Start with a common layout, then customize columns as needed.
        </p>

        {presets.map((p) => (
          <label key={p.key} className={styles.presetCard}>
            <input
              type="radio"
              name="preset"
              value={p.key}
              checked={selected === p.key}
              onChange={() => setSelected(p.key)}
            />
            <div>
              <div style={{ fontWeight: 500 }}>{p.name}</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {p.column_count} columns &middot; {p.description}
              </div>
            </div>
          </label>
        ))}

        {hasExistingColumns && (
          <div className={styles.warningBox}>
            This will replace all existing columns.
          </div>
        )}

        <div className={styles.dialogActions}>
          <button className="btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={() => onCopy(selected)}
            disabled={!selected || isPending}
          >
            {isPending ? "Copying..." : "Copy preset"}
          </button>
        </div>
      </div>
    </div>
  );
}
