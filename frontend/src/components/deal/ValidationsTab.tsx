import { useState } from "react";
import { useToast } from "../Toast";
import { createNode, updateNode, deleteNode } from "../../api/dag";
import type { Variable } from "../../types";

interface DagNodeLite {
  id: number;
  key: string;
  name: string;
  node_type: string;
  stream: string;
  formula: string | null;
  comparison_variable: string | null;
  tolerance: number | null;
}

interface DagData {
  version: { id: number; version_number: number };
  nodes: DagNodeLite[];
  edges: Array<{ id: number; source_node_id: number; target_node_id: number }>;
}

interface Props {
  dag: DagData;
  mappedVariables: Variable[];
  isEditable: boolean;
  dealId: number;
  onRefreshDag: () => void;
}

function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 80);
}

function uniqueKey(base: string, nodes: DagNodeLite[]): string {
  const taken = new Set(nodes.map((n) => n.key));
  if (!taken.has(base)) return base;
  let i = 2;
  while (taken.has(`${base}_${i}`)) i++;
  return `${base}_${i}`;
}

export function ValidationsTab({ dag, mappedVariables, isEditable, dealId, onRefreshDag }: Props) {
  const { toast } = useToast();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<DagNodeLite | null>(null);

  const validations = dag.nodes.filter((n) => n.node_type === "validation");
  const calcNodes = dag.nodes.filter(
    (n) => n.node_type !== "validation" && n.node_type !== "input_value",
  );
  const nodeByKey = new Map(dag.nodes.map((n) => [n.key, n] as const));

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (node: DagNodeLite) => {
    setEditing(node);
    setDialogOpen(true);
  };

  const handleDelete = async (node: DagNodeLite) => {
    if (!window.confirm(`Delete validation "${node.name}"?`)) return;
    try {
      await deleteNode(node.id);
      onRefreshDag();
      toast("Validation deleted");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Delete failed", "error");
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          {validations.length} validation{validations.length === 1 ? "" : "s"} configured. Each check compares a DAG
          node's computed value against a tape-reported variable within a tolerance.
        </div>
        {isEditable && (
          <button className="btn btn-primary" onClick={openCreate}>
            + Add validation
          </button>
        )}
      </div>

      {validations.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No validations configured</div>
          <div className="empty-state-text">
            Add a validation to compare a calculated DAG node against a tape-reported variable.
          </div>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Calculated node</th>
              <th>Tape variable</th>
              <th style={{ textAlign: "right" }}>Tolerance</th>
              {isEditable && <th style={{ width: 140 }}></th>}
            </tr>
          </thead>
          <tbody>
            {validations.map((v) => {
              const calcNode = v.formula ? nodeByKey.get(v.formula.trim()) : null;
              return (
                <tr key={v.id}>
                  <td>{v.name}</td>
                  <td>
                    {calcNode ? (
                      <span>
                        {calcNode.name}
                        <code style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 6 }}>
                          ({calcNode.key})
                        </code>
                      </span>
                    ) : (
                      <code style={{ fontSize: 12, color: "var(--accent-blue)" }}>{v.formula ?? "—"}</code>
                    )}
                  </td>
                  <td>
                    {v.comparison_variable ? (
                      <code style={{ fontSize: 12, color: "var(--accent-yellow, #fbbf24)" }}>
                        {v.comparison_variable}
                      </code>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontSize: 12 }}>— not set —</span>
                    )}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                    {v.tolerance != null ? String(v.tolerance) : "—"}
                  </td>
                  {isEditable && (
                    <td>
                      <button className="btn btn-sm btn-ghost" onClick={() => openEdit(v)}>
                        Edit
                      </button>
                      <button
                        className="btn btn-sm btn-ghost"
                        onClick={() => handleDelete(v)}
                        style={{ marginLeft: 4 }}
                      >
                        Delete
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {dialogOpen && (
        <ValidationDialog
          initial={editing}
          calcNodes={calcNodes}
          mappedVariables={mappedVariables}
          allNodes={dag.nodes}
          onClose={() => setDialogOpen(false)}
          onSave={async (payload) => {
            try {
              if (editing) {
                await updateNode(editing.id, payload, dealId);
                toast("Validation updated");
              } else {
                await createNode(dealId, payload);
                toast("Validation created");
              }
              setDialogOpen(false);
              onRefreshDag();
            } catch (e) {
              toast(e instanceof Error ? e.message : "Save failed", "error");
            }
          }}
        />
      )}
    </div>
  );
}

// ── Create / Edit dialog ─────────────────────────────────────────

interface DialogProps {
  initial: DagNodeLite | null;
  calcNodes: DagNodeLite[];
  mappedVariables: Variable[];
  allNodes: DagNodeLite[];
  onClose: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
}

function ValidationDialog({ initial, calcNodes, mappedVariables, allNodes, onClose, onSave }: DialogProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [calcKey, setCalcKey] = useState(initial?.formula?.trim() ?? "");
  const [tapeVar, setTapeVar] = useState(initial?.comparison_variable ?? "");
  const [tolerance, setTolerance] = useState(
    initial?.tolerance != null ? String(initial.tolerance) : "0.01",
  );

  const canSave = name.trim().length > 0 && calcKey && tapeVar;

  const handleSave = () => {
    if (!canSave) return;
    if (initial) {
      // Edit: update the existing node in place.
      onSave({
        name: name.trim(),
        formula: calcKey,
        comparison_variable: tapeVar,
        tolerance: tolerance || "0.01",
      });
    } else {
      // Create: derive a unique key from the name.
      const base = slugify(name) || `validation_${Date.now()}`;
      const key = uniqueKey(base, allNodes);
      onSave({
        node_key: key,
        name: name.trim(),
        node_type: "validation",
        stream: "validation",
        formula: calcKey,
        comparison_variable: tapeVar,
        tolerance: tolerance || "0.01",
      });
    }
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()} style={{ minWidth: 480 }}>
        <div className="dialog-title">{initial ? "Edit validation" : "Add validation"}</div>

        <div className="form-field">
          <label className="form-label">Name</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Class A Interest Check"
            autoFocus
          />
        </div>

        <div className="form-field">
          <label className="form-label">Calculated side (pick a DAG node)</label>
          <select
            className="select"
            value={calcKey}
            onChange={(e) => setCalcKey(e.target.value)}
            style={{ width: "100%", fontFamily: "var(--font-mono)" }}
          >
            <option value="">— pick a calc / distribution node —</option>
            {calcNodes.map((n) => (
              <option key={n.id} value={n.key}>
                {n.name} ({n.key})
              </option>
            ))}
          </select>
          <div className="form-help" style={{ marginTop: 4 }}>
            The DAG-computed value that will be compared against the tape.
          </div>
        </div>

        <div className="form-field">
          <label className="form-label">Tape side (pick a mapped variable)</label>
          <select
            className="select"
            value={tapeVar}
            onChange={(e) => setTapeVar(e.target.value)}
            style={{ width: "100%", fontFamily: "var(--font-mono)" }}
          >
            <option value="">— pick a tape variable —</option>
            {mappedVariables.map((v) => (
              <option key={v.id} value={v.name}>
                {v.display_name ? `${v.display_name} (${v.name})` : v.name}
              </option>
            ))}
          </select>
          <div className="form-help" style={{ marginTop: 4 }}>
            Tape-reported variable the calculated value is checked against.
          </div>
        </div>

        <div className="form-field">
          <label className="form-label">Tolerance (absolute)</label>
          <input
            className="input"
            value={tolerance}
            onChange={(e) => setTolerance(e.target.value)}
            placeholder="0.01"
            style={{ fontFamily: "var(--font-mono)", maxWidth: 160 }}
          />
        </div>

        <div className="btn-group" style={{ marginTop: 16 }}>
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={!canSave}>
            {initial ? "Save changes" : "Create validation"}
          </button>
        </div>
      </div>
    </div>
  );
}
