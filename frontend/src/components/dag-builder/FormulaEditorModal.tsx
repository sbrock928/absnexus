import { useState, useRef } from "react";
import type { FormulaToken } from "./DagGraphView";

interface Props {
  initial: string;
  tokens: FormulaToken[];
  onSave: (formula: string) => void;
  onCancel: () => void;
}

export function FormulaEditorModal({ initial, tokens, onSave, onCancel }: Props) {
  const [formula, setFormula] = useState(initial);
  const ref = useRef<HTMLTextAreaElement>(null);

  const insertToken = (name: string, appendParen: boolean) => {
    const el = ref.current;
    if (!el) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const before = formula.slice(0, start);
    const after = formula.slice(end);
    const sep = before.length > 0 && !before.endsWith(" ") && !before.endsWith("(") ? " " : "";
    const insert = appendParen ? name + "(" : name;
    const next = before + sep + insert + after;
    setFormula(next);
    requestAnimationFrame(() => {
      const pos = (before + sep + insert).length;
      el.focus();
      el.setSelectionRange(pos, pos);
    });
  };

  const variables = tokens.filter((t) => t.category === "variable");
  const nodes = tokens.filter((t) => t.category === "node");
  const functions = tokens.filter((t) => t.category === "function");

  return (
    <div className="dialog-overlay" onClick={onCancel}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 560, maxWidth: 700 }}>
        <div className="dialog-title">Edit formula</div>

        <div className="form-field">
          <label className="form-label">Formula</label>
          <textarea
            ref={ref}
            className="textarea"
            value={formula}
            onChange={(e) => setFormula(e.target.value)}
            rows={4}
            spellCheck={false}
            autoFocus
            style={{ fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace", fontSize: 13 }}
          />
        </div>

        {/* Token palette */}
        <div style={{
          maxHeight: 220,
          overflowY: "auto",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: 10,
          background: "var(--bg-tertiary)",
          marginBottom: 16,
        }}>
          {variables.length > 0 && (
            <TokenSection label="Variables" tokens={variables} color="var(--accent-green)" bgAlpha="74, 222, 128" onClick={(t) => insertToken(t.name, false)} />
          )}
          {nodes.length > 0 && (
            <TokenSection label="Nodes" tokens={nodes} color="var(--accent-blue)" bgAlpha="74, 158, 255" onClick={(t) => insertToken(t.name, false)} />
          )}
          {functions.length > 0 && (
            <TokenSection label="Functions" tokens={functions} color="var(--accent-purple)" bgAlpha="167, 139, 250" onClick={(t) => insertToken(t.name, true)} />
          )}
        </div>

        <div className="btn-group">
          <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onSave(formula.trim())}>
            Save formula
          </button>
        </div>
      </div>
    </div>
  );
}

function TokenSection({ label, tokens, color, bgAlpha, onClick }: {
  label: string;
  tokens: FormulaToken[];
  color: string;
  bgAlpha: string;
  onClick: (t: FormulaToken) => void;
}) {
  const [search, setSearch] = useState("");
  const filtered = search
    ? tokens.filter((t) => t.name.includes(search.toLowerCase()) || t.label.toLowerCase().includes(search.toLowerCase()))
    : tokens;

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.4px", color: "var(--text-muted)" }}>
          {label} ({tokens.length})
        </span>
        {tokens.length > 10 && (
          <input
            placeholder={`Filter ${label.toLowerCase()}...`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              fontSize: 11, padding: "2px 6px", background: "var(--bg-secondary)", border: "1px solid var(--border)",
              borderRadius: 3, color: "var(--text-primary)", width: 140,
            }}
          />
        )}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
        {filtered.slice(0, 50).map((t) => (
          <button
            key={t.name}
            title={t.label}
            onClick={() => onClick(t)}
            style={{
              padding: "3px 8px",
              fontSize: 11,
              fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
              background: `rgba(${bgAlpha}, 0.1)`,
              border: `1px solid rgba(${bgAlpha}, 0.25)`,
              borderRadius: 3,
              color,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {t.name}
          </button>
        ))}
        {filtered.length > 50 && (
          <span style={{ fontSize: 11, color: "var(--text-muted)", padding: "3px 4px" }}>
            +{filtered.length - 50} more
          </span>
        )}
      </div>
    </div>
  );
}
