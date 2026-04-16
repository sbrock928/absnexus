import { useState, useEffect, useRef } from "react";
import type { DagNodeData } from "./types";
import type { FormulaToken } from "./DagGraphView";
import styles from "./NodePropertiesPanel.module.css";

interface Props {
  node: DagNodeData;
  onUpdate: (fields: Partial<DagNodeData>) => void;
  onDelete: () => void;
  onDeactivate: () => void;
  onReactivate: () => void;
  dependencies: string[];
  downstream: string[];
  availableTokens?: FormulaToken[];
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
}: Props) {
  const formulaRef = useRef<HTMLTextAreaElement>(null);
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

      {/* Formula — calc, dist, validation */}
      {node.node_type !== "input" && (
        <div className={styles.field}>
          <label className={styles.label}>Formula</label>
          <textarea
            ref={formulaRef}
            className={styles.textarea}
            value={formula}
            onChange={(e) => { setFormula(e.target.value); markDirty(); }}
            rows={3}
            spellCheck={false}
            placeholder="e.g. total_collections * svc_fee_rate"
          />
          {availableTokens.length > 0 && (
            <div className={styles.tokenPalette}>
              <div className={styles.tokenSection}>
                <div className={styles.tokenSectionLabel}>Variables</div>
                <div className={styles.tokenGrid}>
                  {availableTokens.filter(t => t.category === "variable").map(t => (
                    <button
                      key={t.name}
                      className={styles.tokenBtn}
                      title={t.label}
                      onClick={() => {
                        const el = formulaRef.current;
                        if (!el) return;
                        const start = el.selectionStart;
                        const end = el.selectionEnd;
                        const before = formula.slice(0, start);
                        const after = formula.slice(end);
                        const sep = before.length > 0 && !before.endsWith(" ") && !before.endsWith("(") ? " " : "";
                        const newFormula = before + sep + t.name + after;
                        setFormula(newFormula);
                        markDirty();
                        requestAnimationFrame(() => {
                          const pos = (before + sep + t.name).length;
                          el.focus();
                          el.setSelectionRange(pos, pos);
                        });
                      }}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>
              <div className={styles.tokenSection}>
                <div className={styles.tokenSectionLabel}>Nodes</div>
                <div className={styles.tokenGrid}>
                  {availableTokens.filter(t => t.category === "node").map(t => (
                    <button
                      key={t.name}
                      className={`${styles.tokenBtn} ${styles.tokenNode}`}
                      title={t.label}
                      onClick={() => {
                        const el = formulaRef.current;
                        if (!el) return;
                        const start = el.selectionStart;
                        const end = el.selectionEnd;
                        const before = formula.slice(0, start);
                        const after = formula.slice(end);
                        const sep = before.length > 0 && !before.endsWith(" ") && !before.endsWith("(") ? " " : "";
                        const newFormula = before + sep + t.name + after;
                        setFormula(newFormula);
                        markDirty();
                        requestAnimationFrame(() => {
                          const pos = (before + sep + t.name).length;
                          el.focus();
                          el.setSelectionRange(pos, pos);
                        });
                      }}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>
              <div className={styles.tokenSection}>
                <div className={styles.tokenSectionLabel}>Functions</div>
                <div className={styles.tokenGrid}>
                  {availableTokens.filter(t => t.category === "function").map(t => (
                    <button
                      key={t.name}
                      className={`${styles.tokenBtn} ${styles.tokenFunc}`}
                      title={t.label}
                      onClick={() => {
                        const el = formulaRef.current;
                        if (!el) return;
                        const start = el.selectionStart;
                        const end = el.selectionEnd;
                        const before = formula.slice(0, start);
                        const after = formula.slice(end);
                        const sep = before.length > 0 && !before.endsWith(" ") && !before.endsWith("(") ? " " : "";
                        const insert = t.name + "(";
                        const newFormula = before + sep + insert + after;
                        setFormula(newFormula);
                        markDirty();
                        requestAnimationFrame(() => {
                          const pos = (before + sep + insert).length;
                          el.focus();
                          el.setSelectionRange(pos, pos);
                        });
                      }}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
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

      {/* Input source — input nodes only */}
      {node.node_type === "input" && (
        <div className={styles.field}>
          <label className={styles.label}>Input source</label>
          <div className={styles.sourceInfo}>
            {node.input_source === "tranche"
              ? `Tranche field: ${node.tranche_field ?? "not set"}`
              : node.variable_id
              ? `Tape variable #${node.variable_id}`
              : "Not configured"}
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
            <input
              className={styles.input}
              value={comparisonVar}
              onChange={(e) => { setComparisonVar(e.target.value); markDirty(); }}
              onKeyDown={handleKeyDown}
              placeholder="e.g. reported_oc"
              style={{ fontFamily: "var(--font-mono)" }}
            />
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
          onClick={() => {
            if (window.confirm(`Delete node "${node.label}"? This removes all connected edges.`)) {
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
