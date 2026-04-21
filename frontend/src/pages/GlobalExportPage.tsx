import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "../components/Toast";
import { useConfirm } from "../components/ConfirmDialog";
import {
  listTemplates,
  getTemplate,
  createColumn,
  updateGlobalColumn,
  deleteGlobalColumn,
  reorderGlobalColumns,
  type GlobalColumn,
  type GlobalTemplate,
} from "../api/globalExport";

const VALUE_TYPES = [
  { value: "distribution_node", label: "Distribution node" },
  { value: "literal", label: "Literal value" },
  { value: "run_meta", label: "Run metadata" },
  { value: "deal_meta", label: "Deal metadata" },
  { value: "deal_account", label: "Deal account (trust account number)" },
];

export function GlobalExportPage() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const confirm = useConfirm();
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<GlobalColumn | null>(null);

  const { data: templates = [] } = useQuery({
    queryKey: ["global-templates"],
    queryFn: listTemplates,
  });

  // Auto-select first template
  const activeId = selectedTemplateId ?? templates[0]?.id ?? null;

  const { data: templateData } = useQuery({
    queryKey: ["global-template", activeId],
    queryFn: () => getTemplate(activeId!),
    enabled: activeId !== null,
  });

  const columns = templateData?.columns ?? [];

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["global-template", activeId] });
  };

  const createMut = useMutation({
    mutationFn: (body: Partial<GlobalColumn>) => createColumn(activeId!, body),
    onSuccess: () => { invalidate(); setShowAdd(false); toast("Column added"); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, fields }: { id: number; fields: Partial<GlobalColumn> }) =>
      updateGlobalColumn(id, fields),
    onSuccess: () => { invalidate(); setEditing(null); toast("Column updated"); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const deleteMut = useMutation({
    mutationFn: deleteGlobalColumn,
    onSuccess: () => { invalidate(); toast("Column deleted"); },
    onError: (e: Error) => toast(e.message, "error"),
  });

  const moveUp = (idx: number) => {
    if (idx <= 0) return;
    const ids = columns.map((c) => c.id);
    [ids[idx - 1], ids[idx]] = [ids[idx], ids[idx - 1]];
    reorderGlobalColumns(activeId!, ids).then(invalidate);
  };

  const moveDown = (idx: number) => {
    if (idx >= columns.length - 1) return;
    const ids = columns.map((c) => c.id);
    [ids[idx], ids[idx + 1]] = [ids[idx + 1], ids[idx]];
    reorderGlobalColumns(activeId!, ids).then(invalidate);
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Export Templates</div>
          <div className="page-subtitle">
            {templates.length} global templates — shared across all deals
          </div>
        </div>
      </div>

      {/* Template tabs */}
      <div className="tabs">
        {templates.map((t) => (
          <button
            key={t.id}
            className={`tab ${activeId === t.id ? "active" : ""}`}
            onClick={() => setSelectedTemplateId(t.id)}
          >
            {t.name}
          </button>
        ))}
      </div>

      {activeId && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <div style={{ color: "var(--text-secondary)", fontSize: 13 }}>
              {templateData?.template.description ?? ""}
            </div>
            <button className="btn btn-primary" onClick={() => { setEditing(null); setShowAdd(true); }}>
              + Column
            </button>
          </div>

          {columns.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-title">No columns defined</div>
              <div className="empty-state-text">Add columns to define this template's CSV layout.</div>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Header</th>
                  <th>Type</th>
                  <th>Source</th>
                  <th>Format</th>
                  <th style={{ width: 160 }}></th>
                </tr>
              </thead>
              <tbody>
                {columns.map((c, idx) => (
                  <tr key={c.id}>
                    <td style={{ color: "var(--text-muted)" }}>{idx + 1}</td>
                    <td style={{ fontFamily: "monospace", fontWeight: 500 }}>{c.header_label}</td>
                    <td>
                      <span className={`badge ${c.value_type === "distribution_node" ? "badge-active" : "badge-system"}`}>
                        {c.value_type}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                      {c.value_type === "distribution_node" && (
                        <span style={{ color: "var(--accent-purple)", fontStyle: "italic" }}>Mapped per deal</span>
                      )}
                      {c.value_type === "literal" && (c.literal_value ?? "—")}
                      {c.value_type === "run_meta" && (c.meta_field ?? "—")}
                      {c.value_type === "deal_meta" && (c.meta_field ?? "—")}
                      {c.value_type === "deal_account" && (c.meta_field ? `account: ${c.meta_field}` : "—")}
                    </td>
                    <td style={{ fontSize: 12 }}>
                      {c.format_type}
                      {c.decimal_places != null && ` (${c.decimal_places} dp)`}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => moveUp(idx)} disabled={idx === 0}>
                          &uarr;
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => moveDown(idx)} disabled={idx === columns.length - 1}>
                          &darr;
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setEditing(c)}>Edit</button>
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: "var(--accent-red)" }}
                          onClick={async () => { if (await confirm({ message: `Delete "${c.header_label}"?`, confirmLabel: "Delete" })) deleteMut.mutate(c.id); }}
                        >
                          Del
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {/* Add / Edit Column Dialog */}
      {(showAdd || editing) && (
        <ColumnDialog
          column={editing}
          onSave={(payload) => {
            if (editing) {
              updateMut.mutate({ id: editing.id, fields: payload });
            } else {
              createMut.mutate(payload);
            }
          }}
          onCancel={() => { setShowAdd(false); setEditing(null); }}
        />
      )}
    </div>
  );
}

function ColumnDialog({
  column,
  onSave,
  onCancel,
}: {
  column: GlobalColumn | null;
  onSave: (payload: Partial<GlobalColumn>) => void;
  onCancel: () => void;
}) {
  const isEdit = !!column;
  const [headerLabel, setHeaderLabel] = useState(column?.header_label ?? "");
  const [valueType, setValueType] = useState(column?.value_type ?? "literal");
  const [literalValue, setLiteralValue] = useState(column?.literal_value ?? "");
  const [metaField, setMetaField] = useState(column?.meta_field ?? "");
  const [formatType, setFormatType] = useState(column?.format_type ?? "text");
  const [decimalPlaces, setDecimalPlaces] = useState(column?.decimal_places?.toString() ?? "");

  const handleSave = () => {
    if (!headerLabel.trim()) return;
    onSave({
      header_label: headerLabel.trim(),
      value_type: valueType as GlobalColumn["value_type"],
      literal_value: valueType === "literal" ? literalValue : null,
      meta_field:
        valueType === "run_meta" || valueType === "deal_meta" || valueType === "deal_account"
          ? metaField
          : null,
      format_type: formatType,
      decimal_places: decimalPlaces ? Number(decimalPlaces) : null,
    });
  };

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 460 }}>
        <div className="dialog-title">{isEdit ? "Edit column" : "Add column"}</div>

        <div className="form-field">
          <label className="form-label">Header label</label>
          <input className="input" value={headerLabel} onChange={(e) => setHeaderLabel(e.target.value)} placeholder="e.g. AMOUNT" autoFocus />
        </div>

        <div className="form-field">
          <label className="form-label">Value type</label>
          <select className="select" value={valueType} onChange={(e) => setValueType(e.target.value)}>
            {VALUE_TYPES.map((vt) => (
              <option key={vt.value} value={vt.value}>{vt.label}</option>
            ))}
          </select>
        </div>

        {valueType === "literal" && (
          <div className="form-field">
            <label className="form-label">Literal value</label>
            <input className="input" value={literalValue} onChange={(e) => setLiteralValue(e.target.value)} placeholder="e.g. DISTRIBUTION" />
          </div>
        )}

        {valueType === "run_meta" && (
          <div className="form-field">
            <label className="form-label">Meta field</label>
            <select className="select" value={metaField} onChange={(e) => setMetaField(e.target.value)}>
              <option value="">Select...</option>
              <option value="run_code">Run code</option>
              <option value="payment_date">Payment date (report period)</option>
              <option value="report_period">Report period</option>
              <option value="distribution_date">Distribution date</option>
              <option value="determination_date">Determination date</option>
              <option value="days_in_period_actual">Days in period (calendar)</option>
              <option value="days_in_period_30_360">Days in period (30/360)</option>
            </select>
          </div>
        )}

        {valueType === "deal_meta" && (
          <div className="form-field">
            <label className="form-label">Meta field</label>
            <select className="select" value={metaField} onChange={(e) => setMetaField(e.target.value)}>
              <option value="">Select...</option>
              <option value="deal_id">Deal ID</option>
              <option value="deal_name">Deal name</option>
              <option value="product_type">Product type</option>
              <option value="issuer_name">Issuer name</option>
              <option value="deal_key">Deal key</option>
              <option value="closing_date">Closing date</option>
              <option value="initial_cutoff_date">Initial cutoff date</option>
              <option value="initial_distribution_date">Initial distribution date</option>
              <option value="cutoff_pool_balance">Cutoff pool balance</option>
            </select>
          </div>
        )}

        {valueType === "deal_account" && (
          <div className="form-field">
            <label className="form-label">Account label</label>
            <input
              className="input"
              value={metaField}
              onChange={(e) => setMetaField(e.target.value)}
              placeholder="e.g. Main, Collection, Reserve"
            />
            <div className="form-help" style={{ marginTop: 4 }}>
              Matches (case-insensitive) a trust account label defined on each deal's Info tab. The account number is emitted on export.
            </div>
          </div>
        )}

        {valueType === "distribution_node" && (
          <div className="form-help" style={{ marginTop: 8, marginBottom: 8 }}>
            Distribution node columns are mapped to specific DAG nodes at the deal level.
          </div>
        )}

        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Format</label>
            <select className="select" value={formatType} onChange={(e) => setFormatType(e.target.value)}>
              <option value="text">Text</option>
              <option value="decimal">Decimal</option>
              <option value="integer">Integer</option>
            </select>
          </div>
          {formatType === "decimal" && (
            <div className="form-field">
              <label className="form-label">Decimal places</label>
              <input className="input" type="number" value={decimalPlaces} onChange={(e) => setDecimalPlaces(e.target.value)} placeholder="2" min={0} max={10} />
            </div>
          )}
        </div>

        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={!headerLabel.trim()}>
            {isEdit ? "Update" : "Add column"}
          </button>
        </div>
      </div>
    </div>
  );
}
