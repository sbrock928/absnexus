import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/auth";
import {
  fetchNodes,
  fetchEdges,
  fetchVersions,
  createNode,
  updateNode,
  deleteNode,
  deactivateNode,
  reactivateNode,
  createEdge,
  deleteEdge,
  saveDag,
  revertDag,
  type DagNode,
  type DagEdge,
  type DagVersion,
} from "@/api/dag";
import { DagGraphView } from "@/components/dag-builder/DagGraphView";
import styles from "./DagEditorPage.module.css";

export function DagEditorPage() {
  const { dealId } = useParams<{ dealId: string }>();
  const id = Number(dealId);
  const { isModeler } = useAuth();
  const queryClient = useQueryClient();

  const [viewMode, setViewMode] = useState<"table" | "graph">("table");
  const [stream, setStream] = useState<"distribution" | "validation">("distribution");
  const [showAddNode, setShowAddNode] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [saveDesc, setSaveDesc] = useState("");
  const [showSave, setShowSave] = useState(false);

  // Fetch data
  const { data: allNodes = [] } = useQuery({
    queryKey: ["dag-nodes", id],
    queryFn: () => fetchNodes(id),
  });

  const { data: edges = [] } = useQuery({
    queryKey: ["dag-edges", id],
    queryFn: () => fetchEdges(id),
  });

  const { data: versions = [] } = useQuery({
    queryKey: ["dag-versions", id],
    queryFn: () => fetchVersions(id),
  });

  const currentVersion = versions.length > 0 ? versions[0] : null;

  // Filter by stream for table view
  const filteredNodes = allNodes.filter((n) => n.stream === stream);
  const inputNodes = filteredNodes.filter((n) => n.node_type === "input");
  const calcNodes = filteredNodes.filter((n) => n.node_type === "calculation");
  const distNodes = filteredNodes.filter((n) => n.node_type === "distribution");
  const valNodes = filteredNodes.filter((n) => n.node_type === "validation");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["dag-nodes", id] });
    queryClient.invalidateQueries({ queryKey: ["dag-edges", id] });
    queryClient.invalidateQueries({ queryKey: ["dag-versions", id] });
  };

  // Mutations
  const createNodeMut = useMutation({
    mutationFn: (payload: Partial<DagNode>) => createNode(id, payload),
    onSuccess: invalidate,
  });

  const updateNodeMut = useMutation({
    mutationFn: ({ nodeId, fields }: { nodeId: number; fields: Record<string, any> }) =>
      updateNode(nodeId, fields),
    onSuccess: invalidate,
  });

  const deleteNodeMut = useMutation({
    mutationFn: (nodeId: number) => deleteNode(nodeId),
    onSuccess: invalidate,
  });

  const deactivateMut = useMutation({
    mutationFn: (nodeId: number) => deactivateNode(nodeId),
    onSuccess: invalidate,
  });

  const reactivateMut = useMutation({
    mutationFn: (nodeId: number) => reactivateNode(nodeId),
    onSuccess: invalidate,
  });

  const createEdgeMut = useMutation({
    mutationFn: (payload: { source_node_id: number; target_node_id: number }) =>
      createEdge(id, payload),
    onSuccess: invalidate,
  });

  const deleteEdgeMut = useMutation({
    mutationFn: (edgeId: number) => deleteEdge(edgeId),
    onSuccess: invalidate,
  });

  const saveMut = useMutation({
    mutationFn: (desc: string) => saveDag(id, desc),
    onSuccess: () => {
      invalidate();
      setShowSave(false);
      setSaveDesc("");
    },
  });

  const revertMut = useMutation({
    mutationFn: (versionId: number) => revertDag(id, versionId),
    onSuccess: () => {
      invalidate();
      setShowHistory(false);
    },
  });

  // ── Add Node Dialog ────────────────────────────────────────

  const [newNodeKey, setNewNodeKey] = useState("");
  const [newNodeName, setNewNodeName] = useState("");
  const [newNodeType, setNewNodeType] = useState("calculation");
  const [newFormula, setNewFormula] = useState("");
  const [newPaymentType, setNewPaymentType] = useState("");
  const [newTolerance, setNewTolerance] = useState("0.01");
  const [newComparisonVar, setNewComparisonVar] = useState("");

  const resetAddForm = () => {
    setNewNodeKey("");
    setNewNodeName("");
    setNewNodeType("calculation");
    setNewFormula("");
    setNewPaymentType("");
    setNewTolerance("0.01");
    setNewComparisonVar("");
  };

  const handleAddNode = () => {
    if (!newNodeKey || !newNodeName) return;
    const payload: any = {
      node_key: newNodeKey,
      name: newNodeName,
      node_type: newNodeType,
      stream,
      position_x: 200 + Math.random() * 300,
      position_y: 100 + allNodes.length * 60,
    };
    if (newNodeType !== "input" && newFormula) {
      payload.formula = newFormula;
    }
    if (newNodeType === "distribution" && newPaymentType) {
      payload.payment_type = newPaymentType;
    }
    if (newNodeType === "validation") {
      payload.tolerance = newTolerance;
      if (newComparisonVar) payload.comparison_var = newComparisonVar;
    }
    createNodeMut.mutate(payload, {
      onSuccess: () => {
        setShowAddNode(false);
        resetAddForm();
      },
    });
  };

  // Node type colors
  const typeColor = (t: string) => {
    if (t === "input") return "#4ade80";
    if (t === "calculation") return "#60a5fa";
    if (t === "distribution") return "#a78bfa";
    if (t === "validation") return "#fbbf24";
    return "var(--text-muted)";
  };

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">DAG editor</div>
          <div className="page-subtitle">
            {currentVersion
              ? `v${currentVersion.version_number} · ${allNodes.length} nodes · ${edges.length} edges`
              : `${allNodes.length} nodes · ${edges.length} edges · not saved yet`}
          </div>
        </div>
        {isModeler && (
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={() => setShowHistory(true)}>
              History
            </button>
            <button className="btn btn-primary" onClick={() => setShowSave(true)}>
              Save
            </button>
          </div>
        )}
      </div>

      {/* Version banner */}
      {currentVersion && (
        <div className={styles.versionBanner}>
          Version {currentVersion.version_number} · {allNodes.length} nodes · {edges.length} edges
          {currentVersion.description && ` · "${currentVersion.description}"`}
        </div>
      )}

      {/* View + stream toggles */}
      <div className={styles.toggleRow}>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className={`btn ${viewMode === "table" ? "btn-primary" : ""}`}
            onClick={() => setViewMode("table")}
          >
            Table view
          </button>
          <button
            className={`btn ${viewMode === "graph" ? "btn-primary" : ""}`}
            onClick={() => setViewMode("graph")}
          >
            Graph view
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {isModeler && (
            <button className="btn" onClick={() => setShowAddNode(true)}>
              + Add node
            </button>
          )}
          <button
            className={`btn ${stream === "distribution" ? "btn-primary" : ""}`}
            onClick={() => setStream("distribution")}
          >
            Distribution
          </button>
          <button
            className={`btn ${stream === "validation" ? "btn-primary" : ""}`}
            onClick={() => setStream("validation")}
          >
            Validation
          </button>
        </div>
      </div>

      {/* Node type legend */}
      <div className={styles.legend}>
        <span><span className={styles.dot} style={{ background: "#4ade80" }} /> input value ({inputNodes.length})</span>
        <span><span className={styles.dot} style={{ background: "#60a5fa" }} /> calculation ({calcNodes.length})</span>
        <span><span className={styles.dot} style={{ background: "#a78bfa" }} /> distribution ({distNodes.length})</span>
        <span><span className={styles.dot} style={{ background: "#fbbf24" }} /> validation ({valNodes.length})</span>
      </div>

      {/* ── Table View ──────────────────────────────────────── */}
      {viewMode === "table" && (
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>Node</th>
              <th>Type</th>
              <th>Stream</th>
              <th>Formula</th>
              <th>Export</th>
              {isModeler && <th></th>}
            </tr>
          </thead>
          <tbody>
            {filteredNodes.map((node, idx) => (
              <tr
                key={node.id}
                style={!node.is_active ? { opacity: 0.4 } : {}}
              >
                <td style={{ color: "var(--text-muted)" }}>{idx + 1}</td>
                <td>
                  <span className={styles.dot} style={{ background: typeColor(node.node_type) }} />
                  <span style={{ fontWeight: 500 }}>{node.name}</span>
                </td>
                <td style={{ fontSize: 12 }}>{node.node_type}</td>
                <td>
                  <span
                    className={`badge ${
                      node.stream === "distribution" ? "badge-green" : "badge-yellow"
                    }`}
                  >
                    {node.stream.toUpperCase()}
                  </span>
                </td>
                <td
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--text-secondary)",
                    maxWidth: 300,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {node.formula ?? "—"}
                </td>
                <td>
                  {node.payment_type && (
                    <span className={styles.exportBadge}>{node.payment_type}</span>
                  )}
                  {!node.payment_type && "—"}
                </td>
                {isModeler && (
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      {node.is_active ? (
                        <button
                          className={styles.actionLink}
                          onClick={() => deactivateMut.mutate(node.id)}
                        >
                          Deactivate
                        </button>
                      ) : (
                        <button
                          className={styles.actionLink}
                          style={{ color: "var(--accent-green)" }}
                          onClick={() => reactivateMut.mutate(node.id)}
                        >
                          Reactivate
                        </button>
                      )}
                      <button
                        className={styles.actionLink}
                        style={{ color: "var(--accent-red)" }}
                        onClick={() => {
                          if (window.confirm(`Delete "${node.name}"?`)) {
                            deleteNodeMut.mutate(node.id);
                          }
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ── Graph View ──────────────────────────────────────── */}
      {viewMode === "graph" && (
        <DagGraphView
          backendNodes={allNodes}
          backendEdges={edges}
          stream={stream}
          onCreateNode={async (type, pos) => {
            const key = `new_${type}_${Date.now()}`;
            const resp = await createNode(id, {
              node_key: key,
              name: `New ${type}`,
              node_type: type,
              stream,
              position_x: pos.x,
              position_y: pos.y,
            } as any);
            invalidate();
            return resp;
          }}
          onUpdateNode={async (nodeId, fields) => {
            await updateNode(nodeId, fields);
            invalidate();
          }}
          onDeleteNode={async (nodeId) => {
            await deleteNode(nodeId);
            invalidate();
          }}
          onDeactivateNode={async (nodeId) => {
            await deactivateNode(nodeId);
            invalidate();
          }}
          onReactivateNode={async (nodeId) => {
            await reactivateNode(nodeId);
            invalidate();
          }}
          onCreateEdge={async (sourceId, targetId) => {
            await createEdge(id, {
              source_node_id: sourceId,
              target_node_id: targetId,
            });
            invalidate();
          }}
          onDeleteEdge={async (edgeId) => {
            await deleteEdge(edgeId);
            invalidate();
          }}
        />
      )}

      {/* ── Add Node Dialog ─────────────────────────────────── */}
      {showAddNode && (
        <div className={styles.overlay} onClick={() => setShowAddNode(false)}>
          <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.dialogTitle}>
              Add node to {stream} stream
            </h2>

            <div className="form-group">
              <label className="form-label">Node key (unique identifier)</label>
              <input
                className="input"
                value={newNodeKey}
                onChange={(e) => setNewNodeKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))}
                placeholder="e.g. class_a_interest_calc"
                style={{ fontFamily: "var(--font-mono)" }}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Display name</label>
              <input
                className="input"
                value={newNodeName}
                onChange={(e) => setNewNodeName(e.target.value)}
                placeholder="e.g. Class A Interest (calc)"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Node type</label>
              <select
                className="select"
                style={{ width: "100%" }}
                value={newNodeType}
                onChange={(e) => setNewNodeType(e.target.value)}
              >
                <option value="input">Input variable</option>
                <option value="calculation">Calculation</option>
                <option value="distribution">Distribution (export)</option>
                {stream === "validation" && (
                  <option value="validation">Validation (check)</option>
                )}
              </select>
            </div>

            {newNodeType !== "input" && (
              <div className="form-group">
                <label className="form-label">Formula</label>
                <textarea
                  className="input"
                  value={newFormula}
                  onChange={(e) => setNewFormula(e.target.value)}
                  placeholder="e.g. class_a_balance * class_a_note_rate / 12"
                  rows={3}
                  style={{ fontFamily: "var(--font-mono)", resize: "vertical" }}
                />
                <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                  Functions: MIN, MAX, ABS, IF, ROUND, CEILING, FLOOR, SUM
                </div>
              </div>
            )}

            {newNodeType === "distribution" && (
              <div className="form-group">
                <label className="form-label">Export field code</label>
                <input
                  className="input"
                  value={newPaymentType}
                  onChange={(e) => setNewPaymentType(e.target.value.toUpperCase())}
                  placeholder="e.g. INT_PMT_A"
                  style={{ fontFamily: "var(--font-mono)" }}
                />
              </div>
            )}

            {newNodeType === "validation" && (
              <>
                <div className="form-group">
                  <label className="form-label">Compare against (tape variable)</label>
                  <input
                    className="input"
                    value={newComparisonVar}
                    onChange={(e) => setNewComparisonVar(e.target.value)}
                    placeholder="e.g. reported_oc"
                    style={{ fontFamily: "var(--font-mono)" }}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Tolerance (absolute)</label>
                  <input
                    className="input"
                    value={newTolerance}
                    onChange={(e) => setNewTolerance(e.target.value)}
                    placeholder="0.01"
                    style={{ fontFamily: "var(--font-mono)" }}
                  />
                </div>
              </>
            )}

            <div className={styles.dialogActions}>
              <button className="btn" onClick={() => { setShowAddNode(false); resetAddForm(); }}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleAddNode}
                disabled={!newNodeKey || !newNodeName || createNodeMut.isPending}
              >
                {createNodeMut.isPending ? "Adding..." : "Add node"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Save Dialog ─────────────────────────────────────── */}
      {showSave && (
        <div className={styles.overlay} onClick={() => setShowSave(false)}>
          <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.dialogTitle}>Save DAG version</h2>
            <div className="form-group">
              <label className="form-label">Description (optional)</label>
              <input
                className="input"
                value={saveDesc}
                onChange={(e) => setSaveDesc(e.target.value)}
                placeholder="e.g. Added OC trigger block"
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveMut.mutate(saveDesc);
                }}
                autoFocus
              />
            </div>
            <div className={styles.dialogActions}>
              <button className="btn" onClick={() => setShowSave(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={() => saveMut.mutate(saveDesc)}
                disabled={saveMut.isPending}
              >
                {saveMut.isPending ? "Saving..." : "Save version"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Version History Dialog ──────────────────────────── */}
      {showHistory && (
        <div className={styles.overlay} onClick={() => setShowHistory(false)}>
          <div className={styles.dialog} style={{ width: 520 }} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.dialogTitle}>Version history</h2>
            {versions.length === 0 && (
              <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "16px 0" }}>
                No versions saved yet. Click "Save" to create the first snapshot.
              </div>
            )}
            {versions.map((v) => (
              <div key={v.id} className={styles.versionItem}>
                <div>
                  <span style={{ fontWeight: 600 }}>v{v.version_number}</span>
                  {v.description && (
                    <span style={{ color: "var(--text-muted)", marginLeft: 8 }}>
                      "{v.description}"
                    </span>
                  )}
                  {v.id === currentVersion?.id && (
                    <span className="badge badge-green" style={{ marginLeft: 8 }}>
                      Current
                    </span>
                  )}
                  {v.is_reverted_from && (
                    <span className="badge badge-yellow" style={{ marginLeft: 8 }}>
                      Reverted from v{v.is_reverted_from}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                  {new Date(v.created_at).toLocaleString()}
                </div>
                {v.id !== currentVersion?.id && isModeler && (
                  <button
                    className={styles.actionLink}
                    style={{ marginTop: 4 }}
                    onClick={() => {
                      if (window.confirm(`Revert to v${v.version_number}? This creates a new version.`)) {
                        revertMut.mutate(v.id);
                      }
                    }}
                  >
                    Revert to this version
                  </button>
                )}
              </div>
            ))}
            <div className={styles.dialogActions}>
              <button className="btn" onClick={() => setShowHistory(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}