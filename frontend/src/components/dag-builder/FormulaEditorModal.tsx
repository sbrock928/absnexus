import { useState } from "react";
import type { FormulaToken } from "./DagGraphView";
import { FormulaChipBuilder } from "./FormulaChipBuilder";

export interface EditableNode {
  id: number;
  node_type: string;
  formula: string;
  comparison_variable: string | null;
  tolerance: string | null;
}

interface MappedVariable {
  id: number;
  name: string;
  display_name: string | null;
}

interface Props {
  node: EditableNode;
  tokens: FormulaToken[];
  mappedVariables?: MappedVariable[];
  onSave: (fields: {
    formula: string;
    comparison_variable?: string | null;
    tolerance?: string | null;
  }) => void;
  onCancel: () => void;
}

export function FormulaEditorModal({
  node,
  tokens,
  mappedVariables = [],
  onSave,
  onCancel,
}: Props) {
  const [formula, setFormula] = useState(node.formula);
  const [comparisonVar, setComparisonVar] = useState(node.comparison_variable ?? "");
  const [tolerance, setTolerance] = useState(node.tolerance ?? "0.01");

  const showCompare = node.node_type === "validation" || node.node_type === "distribution";
  const showTolerance = node.node_type === "validation";

  const handleSave = () => {
    const payload: {
      formula: string;
      comparison_variable?: string | null;
      tolerance?: string | null;
    } = { formula: formula.trim() };
    if (showCompare) {
      payload.comparison_variable = comparisonVar || null;
    }
    if (showTolerance) {
      payload.tolerance = tolerance || null;
    }
    onSave(payload);
  };

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 820, maxWidth: "95vw", width: 820 }}>
        <div className="dialog-title">
          Edit {node.node_type === "validation" ? "validation" : node.node_type === "distribution" ? "distribution" : "formula"}
        </div>

        <div className="form-field">
          <label className="form-label">Formula</label>
          <FormulaChipBuilder value={formula} onChange={setFormula} tokens={tokens} />
        </div>

        {showCompare && (
          <div className="form-field" style={{ marginTop: 12 }}>
            <label className="form-label">Compare against (tape variable)</label>
            <select
              className="input"
              value={comparisonVar}
              onChange={(e) => setComparisonVar(e.target.value)}
              style={{ fontFamily: "var(--font-mono)", width: "100%" }}
            >
              <option value="">— none —</option>
              {mappedVariables.map((v) => (
                <option key={v.id} value={v.name}>
                  {v.display_name ? `${v.display_name} (${v.name})` : v.name}
                </option>
              ))}
            </select>
            <div className="form-help" style={{ marginTop: 4 }}>
              {node.node_type === "validation"
                ? "Tape variable this validation compares the calculated formula against. Pass/fail is determined by the tolerance below."
                : "Tape variable for waterfall reconciliation — leave empty to skip."}
            </div>
          </div>
        )}

        {showTolerance && (
          <div className="form-field" style={{ marginTop: 12 }}>
            <label className="form-label">Tolerance (absolute)</label>
            <input
              className="input"
              value={tolerance}
              onChange={(e) => setTolerance(e.target.value)}
              placeholder="0.01"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </div>
        )}

        <div className="btn-group" style={{ marginTop: 16 }}>
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave}>
            Save changes
          </button>
        </div>
      </div>
    </div>
  );
}
