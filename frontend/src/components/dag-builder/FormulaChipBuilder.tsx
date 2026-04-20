import { useMemo, useState } from "react";
import type { FormulaToken } from "./DagGraphView";

/*
 * Chip-based formula editor. Users cannot type freehand — every piece of the
 * formula (identifiers, operators, numeric literals) must be added by clicking
 * a palette button. This prevents silent typos in calculation formulas.
 *
 * Chips serialize to a whitespace-joined string that the backend FormulaEngine
 * already accepts, so no engine change is required.
 */

export type Chip =
  | { kind: "var"; name: string }
  | { kind: "node"; name: string }
  | { kind: "func"; name: string }
  | { kind: "num"; value: string }
  | { kind: "op"; value: string };

interface Props {
  value: string;
  onChange: (next: string) => void;
  tokens: FormulaToken[];
  placeholder?: string;
}

const OPERATORS = ["+", "-", "*", "/", "(", ")", "=", "<", ">", "<=", ">=", "!=", ",", "AND", "OR", "NOT"];

export function FormulaChipBuilder({ value, onChange, tokens, placeholder }: Props) {
  const tokenCategory = useMemo(() => {
    const map = new Map<string, FormulaToken["category"]>();
    for (const t of tokens) map.set(t.name, t.category);
    return map;
  }, [tokens]);

  const chips = useMemo(() => parseFormula(value, tokenCategory), [value, tokenCategory]);

  const setChips = (next: Chip[]) => onChange(serialize(next));
  const appendChips = (...newChips: Chip[]) => setChips([...chips, ...newChips]);
  const removeAt = (idx: number) => setChips(chips.filter((_, i) => i !== idx));

  const [numInput, setNumInput] = useState("");
  const addNumber = () => {
    const trimmed = numInput.trim();
    if (!trimmed) return;
    if (!/^-?\d+(\.\d+)?$/.test(trimmed)) return;
    appendChips({ kind: "num", value: trimmed });
    setNumInput("");
  };

  const [paletteSearch, setPaletteSearch] = useState("");
  const matches = (t: FormulaToken) => {
    if (!paletteSearch) return true;
    const q = paletteSearch.toLowerCase();
    return t.name.toLowerCase().includes(q) || t.label.toLowerCase().includes(q);
  };
  const byName = (a: FormulaToken, b: FormulaToken) => a.name.localeCompare(b.name);
  const vars = tokens.filter((t) => t.category === "variable" && matches(t)).sort(byName);
  const nodes = tokens.filter((t) => t.category === "node" && matches(t)).sort(byName);
  const fns = tokens.filter((t) => t.category === "function" && matches(t));
  const allVarCount = tokens.filter((t) => t.category === "variable").length;
  const allNodeCount = tokens.filter((t) => t.category === "node").length;
  const allFnCount = tokens.filter((t) => t.category === "function").length;

  return (
    <div>
      {/* Chip strip */}
      <div
        style={{
          minHeight: 44,
          padding: 8,
          background: "var(--bg-input, var(--bg-secondary))",
          border: "1px solid var(--border, var(--border-color))",
          borderRadius: "var(--radius)",
          display: "flex",
          flexWrap: "wrap",
          gap: 4,
          alignItems: "center",
        }}
      >
        {chips.length === 0 && (
          <span style={{ color: "var(--text-muted)", fontSize: 12, fontStyle: "italic" }}>
            {placeholder ?? "Click tokens below to build a formula"}
          </span>
        )}
        {chips.map((chip, idx) => (
          <ChipView key={idx} chip={chip} onRemove={() => removeAt(idx)} />
        ))}
        {chips.length > 0 && (
          <button
            type="button"
            onClick={() => setChips([])}
            title="Clear all"
            style={{
              marginLeft: "auto",
              fontSize: 10,
              color: "var(--text-muted)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Palette */}
      <div
        style={{
          marginTop: 6,
          maxHeight: 480,
          overflowY: "auto",
          border: "1px solid var(--border, var(--border-color))",
          borderRadius: "var(--radius)",
          padding: 10,
          background: "var(--bg-tertiary, var(--bg-sidebar))",
        }}
      >
        {/* Global search — filters variables / nodes / functions in one go */}
        <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 10 }}>
          <input
            type="text"
            placeholder={`Search ${allVarCount} variables, ${allNodeCount} nodes, ${allFnCount} functions…`}
            value={paletteSearch}
            onChange={(e) => setPaletteSearch(e.target.value)}
            autoFocus
            style={{
              flex: 1,
              fontSize: 12,
              padding: "5px 10px",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border, var(--border-color))",
              borderRadius: 4,
              color: "var(--text-primary)",
              fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
            }}
          />
          {paletteSearch && (
            <button
              type="button"
              onClick={() => setPaletteSearch("")}
              style={{
                fontSize: 11,
                padding: "5px 10px",
                background: "transparent",
                border: "1px solid var(--border, var(--border-color))",
                borderRadius: 4,
                color: "var(--text-muted)",
                cursor: "pointer",
              }}
            >
              Clear
            </button>
          )}
        </div>
        {vars.length > 0 && (
          <PaletteSection
            label="Variables"
            color="var(--accent-green)"
            bg="rgba(74,222,128,0.1)"
            border="rgba(74,222,128,0.25)"
            items={vars}
            totalCount={allVarCount}
            onPick={(t) => appendChips({ kind: "var", name: t.name })}
          />
        )}
        {nodes.length > 0 && (
          <PaletteSection
            label="Nodes"
            color="var(--accent-blue)"
            bg="rgba(74,158,255,0.1)"
            border="rgba(74,158,255,0.25)"
            items={nodes}
            totalCount={allNodeCount}
            onPick={(t) => appendChips({ kind: "node", name: t.name })}
          />
        )}
        {fns.length > 0 && (
          <PaletteSection
            label="Functions"
            color="var(--accent-purple)"
            bg="rgba(167,139,250,0.1)"
            border="rgba(167,139,250,0.25)"
            items={fns}
            totalCount={allFnCount}
            onPick={(t) =>
              appendChips(
                { kind: "func", name: t.name },
                { kind: "op", value: "(" },
              )
            }
          />
        )}
        {paletteSearch && vars.length === 0 && nodes.length === 0 && fns.length === 0 && (
          <div style={{ fontSize: 12, color: "var(--text-muted)", fontStyle: "italic", padding: "8px 4px" }}>
            No matches for &ldquo;{paletteSearch}&rdquo;
          </div>
        )}
        <div style={{ marginBottom: 8 }}>
          <div style={sectionLabelStyle}>Operators</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {OPERATORS.map((op) => (
              <button
                key={op}
                type="button"
                onClick={() => appendChips({ kind: "op", value: op })}
                style={{
                  padding: "3px 8px",
                  fontSize: 12,
                  fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
                  background: "rgba(148,163,184,0.1)",
                  border: "1px solid rgba(148,163,184,0.3)",
                  borderRadius: 3,
                  color: "var(--text-primary)",
                  cursor: "pointer",
                  minWidth: 28,
                }}
              >
                {op}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div style={sectionLabelStyle}>Number</div>
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <input
              type="text"
              inputMode="decimal"
              value={numInput}
              onChange={(e) => setNumInput(e.target.value.replace(/[^0-9.\-]/g, ""))}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addNumber();
                }
              }}
              placeholder="e.g. 12"
              style={{
                fontSize: 12,
                padding: "3px 8px",
                background: "var(--bg-secondary)",
                border: "1px solid var(--border, var(--border-color))",
                borderRadius: 3,
                color: "var(--text-primary)",
                width: 120,
                fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
              }}
            />
            <button
              type="button"
              onClick={addNumber}
              disabled={!numInput.trim()}
              style={{
                padding: "3px 10px",
                fontSize: 11,
                background: "var(--accent-blue, #60a5fa)",
                border: "none",
                borderRadius: 3,
                color: "#fff",
                cursor: numInput.trim() ? "pointer" : "not-allowed",
                opacity: numInput.trim() ? 1 : 0.5,
              }}
            >
              Add
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const sectionLabelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.4px",
  color: "var(--text-muted)",
  marginBottom: 4,
};

function ChipView({ chip, onRemove }: { chip: Chip; onRemove: () => void }) {
  const { bg, border, color, text } = chipStyle(chip);
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 4px 2px 8px",
        fontSize: 12,
        fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
        background: bg,
        border: `1px solid ${border}`,
        borderRadius: 3,
        color,
        whiteSpace: "nowrap",
      }}
    >
      {text}
      <button
        type="button"
        onClick={onRemove}
        title="Remove"
        style={{
          background: "transparent",
          border: "none",
          color,
          opacity: 0.6,
          cursor: "pointer",
          fontSize: 12,
          lineHeight: 1,
          padding: "0 2px",
        }}
      >
        ×
      </button>
    </span>
  );
}

function chipStyle(chip: Chip): { bg: string; border: string; color: string; text: string } {
  switch (chip.kind) {
    case "var":
      return { bg: "rgba(74,222,128,0.12)", border: "rgba(74,222,128,0.3)", color: "var(--accent-green)", text: chip.name };
    case "node":
      return { bg: "rgba(74,158,255,0.12)", border: "rgba(74,158,255,0.3)", color: "var(--accent-blue)", text: chip.name };
    case "func":
      return { bg: "rgba(167,139,250,0.12)", border: "rgba(167,139,250,0.3)", color: "var(--accent-purple)", text: chip.name };
    case "num":
      return { bg: "rgba(251,191,36,0.12)", border: "rgba(251,191,36,0.3)", color: "var(--accent-yellow, #fbbf24)", text: chip.value };
    case "op":
      return { bg: "rgba(148,163,184,0.15)", border: "rgba(148,163,184,0.35)", color: "var(--text-primary)", text: chip.value };
  }
}

function PaletteSection({
  label,
  color,
  bg,
  border,
  items,
  totalCount,
  onPick,
}: {
  label: string;
  color: string;
  bg: string;
  border: string;
  items: FormulaToken[];
  totalCount: number;
  onPick: (t: FormulaToken) => void;
}) {
  const filtered = items.length !== totalCount;
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={sectionLabelStyle}>
          {label} {filtered ? `(${items.length} of ${totalCount})` : `(${totalCount})`}
        </span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
        {items.map((t) => (
          <button
            key={t.name}
            type="button"
            title={t.label}
            onClick={() => onPick(t)}
            style={{
              padding: "3px 8px",
              fontSize: 11,
              fontFamily: "'SF Mono', 'Fira Code', 'Consolas', monospace",
              background: bg,
              border: `1px solid ${border}`,
              borderRadius: 3,
              color,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {t.name}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── Parsing / serialization ───────────────────────────────── */

function parseFormula(value: string, tokenCategory: Map<string, FormulaToken["category"]>): Chip[] {
  const chips: Chip[] = [];
  // Order matters: multi-char ops before single-char ops.
  const re = /(\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_]*)|(<=|>=|==|!=)|([+\-*/()=<>,])/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(value)) !== null) {
    if (m[1]) {
      chips.push({ kind: "num", value: m[1] });
    } else if (m[2]) {
      const name = m[2];
      if (name === "AND" || name === "OR" || name === "NOT") {
        chips.push({ kind: "op", value: name });
      } else {
        const cat = tokenCategory.get(name);
        if (cat === "function") chips.push({ kind: "func", name });
        else if (cat === "node") chips.push({ kind: "node", name });
        else chips.push({ kind: "var", name });
      }
    } else if (m[3]) {
      chips.push({ kind: "op", value: m[3] });
    } else if (m[4]) {
      chips.push({ kind: "op", value: m[4] });
    }
  }
  return chips;
}

function serialize(chips: Chip[]): string {
  return chips
    .map((c) => {
      if (c.kind === "num") return c.value;
      if (c.kind === "op") return c.value;
      return c.kind === "func" ? c.name : c.name;
    })
    .join(" ");
}
