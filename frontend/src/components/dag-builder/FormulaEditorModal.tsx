import { useState } from "react";
import type { FormulaToken } from "./DagGraphView";
import { FormulaChipBuilder } from "./FormulaChipBuilder";

interface Props {
  initial: string;
  tokens: FormulaToken[];
  onSave: (formula: string) => void;
  onCancel: () => void;
}

export function FormulaEditorModal({ initial, tokens, onSave, onCancel }: Props) {
  const [formula, setFormula] = useState(initial);

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 560, maxWidth: 700 }}>
        <div className="dialog-title">Edit formula</div>

        <div className="form-field">
          <label className="form-label">Formula</label>
          <FormulaChipBuilder value={formula} onChange={setFormula} tokens={tokens} />
        </div>

        <div className="btn-group" style={{ marginTop: 16 }}>
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onSave(formula.trim())}>
            Save formula
          </button>
        </div>
      </div>
    </div>
  );
}
