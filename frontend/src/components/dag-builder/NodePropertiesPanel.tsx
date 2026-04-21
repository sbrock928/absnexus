import { useState, useEffect } from "react";
import type { DagNodeData } from "./types";
import type { FormulaToken } from "./DagGraphView";
import { FormulaChipBuilder } from "./FormulaChipBuilder";
import { useConfirm } from "../ConfirmDialog";
import styles from "./NodePropertiesPanel.module.css";

export interface MappedVariable {
  id: number;
  name: string;
  display_name: string | null;
}

interface Props {
  node: DagNodeData;
  onUpdate: (fields: Partial<DagNodeData>) => void;
  onDelete: () => void;
  onDeactivate: () => void;
  onReactivate: () => void;
  dependencies: string[];
  downstream: string[];
  availableTokens?: FormulaToken[];
  mappedVariables?: MappedVariable[];
}

const typeColors: Record<string, string> = {
  input: "#4ade80",
  calculation: "#60a5fa",
  distribution: "#a78bfa",
  validation: "#fbbf24",
};

export function NodePropertiesPanel({
  node,
  onUpdate,
  onDelete,
  onDeactivate,
  onReactivate,
  dependencies,
  downstream,
  availableTokens = [],
  mappedVariables = [],
}: Props) {
  const confirm = useConfirm();
  const [name, setName] = useState(node.label);
  const [formula, setFormula] = useState(node.formula ?? "");
  const [description, setDescription] = useState(node.description ?? "");
  const [defaultPrior, setDefaultPrior] = useState(node.default_prior_value ?? "");
  const [tolerance, setTolerance] = useState(node.tolerance ?? "0.01");
  const [comparisonVar, setComparisonVar] = useState(node.comparison_var ?? "");
  const [paymentType, setPaymentType] = useState(node.payment_type ?? "");
  const [dirty, setDirty] = useState(false);

  // Reset form when selected node changes
  useEffect(() => {
    setName(node.label);
    setFormula(node.formula ?? "");
    setDescription(node.description ?? "");
    setDefaultPrior(node.default_prior_value ?? "");
    setTolerance(node.tolerance ?? "0.01");
    setComparisonVar(node.comparison_var ?? "");
    setPaymentType(node.payment_type ?? "");
    setDirty(false);
  }, [node.backendId]);

  const markDirty = () => setDirty(true);

  const save = () => {
    onUpdate({
      label: name,
      formula: formula || undefined,
      description: description || undefined,
      default_prior_value: defaultPrior || undefined,
      tolerance: tolerance || undefined,
      comparison_var: comparisonVar || undefined,
      payment_type: paymentType || undefined,
    });
    setDirty(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      save();
    }
  };

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.title}>Node properties</div>
        <div
          className={styles.typeBadge}
          style={{ borderColor: typeColors[node.node_type] ?? "var(--border-color)" }}
        >
          {node.node_type}
        </div>
      </div>

      {/* Active status */}
      {!node.is_active && (
        <div className={styles.deactivatedBanner}>
          This node is deactivated and will be skipped during execution.
        </div>
      )}

      {/* Name */}
      <div className={styles.field}>
        <label className={styles.label}>Name</label>
        <input
          className={styles.input}
          value={name}
          onChange={(e) => { setName(e.target.value); markDirty(); }}
          onKeyDown={handleKeyDown}
        />
      </div>

      {/* Node key (read-only) */}
      <div className={styles.field}>
        <label className={styles.label}>Node key</label>
        <div className={styles.mono}>{node.node_key}</div>
      </div>

      {/* Formula — calc, dist, validation, or input_value with a formula */}
      {node.node_type !== "input" &&
        !(node.node_type === "input_value" && !node.formula && !!node.variable_id) && (
          <div className={styles.field}>
            <label className={styles.label}>
              {node.node_type === "input_value" ? "Value / formula" : "Formula"}
            </label>
            <FormulaChipBuilder
              value={formula}
              onChange={(next) => { setFormula(next); markDirty(); }}
              tokens={availableTokens}
              placeholder={
                node.node_type === "input_value"
                  ? "e.g. 2500 (literal) or deal_trustee_fee_monthly"
                  : "e.g. total_collections * svc_fee_rate"
              }
            />
          </div>
        )}

      {/* Description */}
      <div className={styles.field}>
        <label className={styles.label}>Description</label>
        <input
          className={styles.input}
          value={description}
          onChange={(e) => { setDescription(e.target.value); markDirty(); }}
          onKeyDown={handleKeyDown}
          placeholder="Optional description"
        />
      </div>

      {/* Input source — input_value nodes only */}
      {(node.node_type === "input" || node.node_type === "input_value") && (
        <div className={styles.field}>
          <label className={styles.label}>Input source</label>
          <div className={styles.sourceInfo}>
            {node.formula
              ? /^-?\d+(\.\d+)?$/.test(node.formula.trim())
                ? `Static value: ${node.formula}`
                : `Expression: ${node.formula}`
              : node.input_source === "tranche"
                ? `Tranche field: ${node.tranche_field ?? "not set"}`
                : node.variable_id
                  ? `Tape variable #${node.variable_id}`
                  : `Context lookup: ${node.node_key}`}
          </div>
        </div>
      )}

      {/* Default prior value — shown when formula references _prior */}
      {node.node_type !== "input" && formula.includes("_prior") && (
        <div className={styles.field}>
          <label className={styles.label}>Default prior value (1st month)</label>
          <input
            className={styles.input}
            value={defaultPrior}
            onChange={(e) => { setDefaultPrior(e.target.value); markDirty(); }}
            onKeyDown={handleKeyDown}
            placeholder="0"
            style={{ fontFamily: "var(--font-mono)" }}
          />
          <div className={styles.formulaHint}>
            Used when no prior month run exists (first-ever execution).
          </div>
        </div>
      )}

      {/* Validation-specific fields */}
      {node.node_type === "validation" && (
        <>
          <div className={styles.field}>
            <label className={styles.label}>Compare against (tape variable)</label>
            <select
              className={styles.input}
              value={comparisonVar}
              onChange={(e) => { setComparisonVar(e.target.value); markDirty(); }}
              style={{ fontFamily: "var(--font-mono)" }}
            >
              <option value="">— none —</option>
              {mappedVariables.map((v) => (
                <option key={v.id} value={v.name}>
                  {v.display_name ? `${v.display_name} (${v.name})` : v.name}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Tolerance (absolute)</label>
            <input
              className={styles.input}
              value={tolerance}
              onChange={(e) => { setTolerance(e.target.value); markDirty(); }}
              onKeyDown={handleKeyDown}
              placeholder="0.01"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
        </>
      )}

      {/* Distribution-specific fields */}
      {node.node_type === "distribution" && (
        <>
          <div className={styles.field}>
            <label className={styles.label}>Export field code</label>
            <input
              className={styles.input}
              value={paymentType}
              onChange={(e) => { setPaymentType(e.target.value); markDirty(); }}
              onKeyDown={handleKeyDown}
              placeholder="e.g. INT_PMT_A"
              style={{ fontFamily: "var(--font-mono)" }}
            />
            <div className={styles.formulaHint}>
              Maps this node's result to a column in the export CSV.
            </div>
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Compare against (tape variable)</label>
            <select
              className={styles.input}
              value={comparisonVar}
              onChange={(e) => { setComparisonVar(e.target.value); markDirty(); }}
              style={{ fontFamily: "var(--font-mono)" }}
            >
              <option value="">— none —</option>
              {mappedVariables.map((v) => (
                <option key={v.id} value={v.name}>
                  {v.display_name ? `${v.display_name} (${v.name})` : v.name}
                </option>
              ))}
            </select>
            <div className={styles.formulaHint}>
              Tape variable for waterfall comparison. Leave empty to skip.
            </div>
          </div>
        </>
      )}

      {/* Save button */}
      {dirty && (
        <button className={styles.saveBtn} onClick={save}>
          Save changes
        </button>
      )}

      {/* Dependencies */}
      <div className={styles.divider} />
      <div className={styles.field}>
        <label className={styles.label}>Dependencies (upstream)</label>
        {dependencies.length > 0 ? (
          <div className={styles.depList}>
            {dependencies.map((d) => (
              <div key={d} className={styles.depItem}>
                <span style={{ color: "var(--text-muted)" }}>←</span> {d}
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.muted}>None (root node)</div>
        )}
      </div>

      <div className={styles.field}>
        <label className={styles.label}>Downstream (depends on this)</label>
        {downstream.length > 0 ? (
          <div className={styles.depList}>
            {downstream.map((d) => (
              <div key={d} className={styles.depItem}>
                <span style={{ color: "var(--text-muted)" }}>→</span> {d}
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.muted}>None (leaf node)</div>
        )}
      </div>

      {/* Actions */}
      <div className={styles.divider} />
      <div className={styles.actions}>
        {node.is_active ? (
          <button className={styles.actionBtn} onClick={onDeactivate}>
            Deactivate node
          </button>
        ) : (
          <button className={styles.actionBtn} onClick={onReactivate}>
            Reactivate node
          </button>
        )}
        <button
          className={styles.deleteBtn}
          onClick={async () => {
            if (await confirm({ message: `Delete node "${node.label}"? This removes all connected edges.`, confirmLabel: "Delete" })) {
              onDelete();
            }
          }}
        >
          Delete node
        </button>
      </div>
    </div>
  );
}
