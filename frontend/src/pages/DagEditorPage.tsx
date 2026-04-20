import { useState, useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/auth";
import { api } from "@/api/client";
import type { Deal, Variable } from "@/types";
import type { FormulaToken } from "@/components/dag-builder/DagGraphView";
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
  importDag,
  type DagNode,
} from "@/api/dag";
import { DagGraphView, NODE_TYPE_TIER, type TierKey } from "@/components/dag-builder/DagGraphView";
import { FormulaEditorModal } from "@/components/dag-builder/FormulaEditorModal";
import { FormulaChipBuilder } from "@/components/dag-builder/FormulaChipBuilder";
import styles from "./DagEditorPage.module.css";

export function DagEditorPage() {
  const { dealId } = useParams<{ dealId: string }>();
  const id = Number(dealId);
  const { isModeler } = useAuth();
  const queryClient = useQueryClient();

  const { data: deal } = useQuery({
    queryKey: ["deal", id],
    queryFn: () => api.get<Deal>(`/deals/${id}`),
  });
  const isArchived = deal?.status === "archived";
  const isEditable = isModeler && !isArchived;

  const [viewMode, setViewMode] = useState<"table" | "graph">("table");
  const [showAddNode, setShowAddNode] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [saveDesc, setSaveDesc] = useState("");
  const [showSave, setShowSave] = useState(false);
  const [editingFormulaNode, setEditingFormulaNode] = useState<{
    id: number;
    node_type: string;
    formula: string;
    comparison_variable: string | null;
    tolerance: string | null;
  } | null>(null);

  // Filter state
  const [searchFilter, setSearchFilter] = useState("");
  const [typeFilters, setTypeFilters] = useState<Record<string, boolean>>({
    input_value: true, calculation: true, distribution: true, validation: true,
  });
  const [focusNodeId, setFocusNodeId] = useState<number | null>(null);
  const [collapsedTiers, setCollapsedTiers] = useState<Set<TierKey>>(new Set());

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

  const { data: variables = [] } = useQuery({
    queryKey: ["variables-all"],
    queryFn: () => api.get<Variable[]>("/variables/"),
  });

  const { data: mappings = [] } = useQuery({
    queryKey: ["deal-mappings", id],
    queryFn: () => api.get<{ id: number; variable_id: number }[]>(`/deals/${id}/mappings`),
  });

  // Tranche setup — surfaces tranche-authoritative values (note rate, original
  // balance, current/prior balances) as formula tokens under the `tranche_` prefix.
  const { data: tranches = [] } = useQuery({
    queryKey: ["deal-tranches", id],
    queryFn: () =>
      api.get<
        Array<{
          id: number;
          class_label: string;
          regulation_type: string;
          note_rate: number | null;
          original_balance: number | null;
          is_active: boolean;
        }>
      >(`/deals/${id}/tranches`),
  });

  const currentVersion = versions.length > 0 ? versions[0] : null;

  // Only variables actually mapped on this deal are usable in formulas and
  // as validation comparison targets.
  const mappedVariables = useMemo(() => {
    const ids = new Set(mappings.map((m) => m.variable_id));
    return variables.filter((v) => ids.has(v.id));
  }, [variables, mappings]);

  // Build token list for formula builder. Tape variables and tranche-derived
  // values are distinct tokens so users can reference either source explicitly.
  const availableTokens: FormulaToken[] = useMemo(() => {
    const tokens: FormulaToken[] = [];
    for (const v of mappedVariables) {
      tokens.push({ name: v.name, label: v.display_name || v.name, category: "variable" });
    }
    // Tranche-derived tokens — mirror the keys produced by TrancheService.
    // One set per active class_label (combined across 144A/RegS): note_rate,
    // original_balance, balance, balance_prior.
    const classSlug = (label: string) =>
      label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    const seenClasses = new Set<string>();
    for (const t of tranches) {
      if (!t.is_active) continue;
      const slug = classSlug(t.class_label);
      if (seenClasses.has(slug)) continue;
      seenClasses.add(slug);
      const prefix = `static_class_${slug}`;
      tokens.push({ name: `${prefix}_note_rate`, label: `Class ${t.class_label} Note Rate (static)`, category: "variable" });
      tokens.push({ name: `${prefix}_original_balance`, label: `Class ${t.class_label} Original Balance (static)`, category: "variable" });
      tokens.push({ name: `${prefix}_balance`, label: `Class ${t.class_label} Balance (static, current)`, category: "variable" });
      tokens.push({ name: `${prefix}_balance_prior`, label: `Class ${t.class_label} Balance (static, prior)`, category: "variable" });
    }
    for (const n of allNodes) {
      tokens.push({ name: n.key, label: n.name, category: "node" });
    }
    for (const fn of ["MIN", "MAX", "ABS", "IF", "ROUND", "CEILING", "FLOOR", "SUM", "PRIOR"]) {
      tokens.push({ name: fn, label: fn, category: "function" });
    }
    return tokens;
  }, [mappedVariables, allNodes, tranches]);

  // Compute focused node ancestors + descendants for drill-down
  const focusedNodeIds: Set<number> | null = useMemo(() => {
    if (!focusNodeId) return null;
    const ids = new Set<number>([focusNodeId]);
    // Build adjacency from edges
    const childrenOf: Record<number, number[]> = {};
    const parentsOf: Record<number, number[]> = {};
    for (const e of edges) {
      (childrenOf[e.source_node_id] ??= []).push(e.target_node_id);
      (parentsOf[e.target_node_id] ??= []).push(e.source_node_id);
    }
    // Walk ancestors
    const walkUp = (nid: number) => {
      for (const pid of (parentsOf[nid] ?? [])) {
        if (!ids.has(pid)) { ids.add(pid); walkUp(pid); }
      }
    };
    // Walk descendants
    const walkDown = (nid: number) => {
      for (const cid of (childrenOf[nid] ?? [])) {
        if (!ids.has(cid)) { ids.add(cid); walkDown(cid); }
      }
    };
    walkUp(focusNodeId);
    walkDown(focusNodeId);
    return ids;
  }, [focusNodeId, edges]);

  // Apply all filters.
  // Validation nodes live on the separate Validations tab (Deal Detail page) —
  // the DAG Builder only covers the payment graph (inputs, calcs, distributions).
  const filteredNodes = allNodes.filter((n) => {
    if (n.node_type === "validation" || n.stream === "validation") return false;
    if (!typeFilters[n.node_type]) return false;
    if (searchFilter && !n.name.toLowerCase().includes(searchFilter.toLowerCase()) && !n.key.toLowerCase().includes(searchFilter.toLowerCase())) return false;
    if (focusedNodeIds && !focusedNodeIds.has(n.id)) return false;
    const tier = NODE_TYPE_TIER[n.node_type] ?? "mid";
    if (collapsedTiers.has(tier)) return false;
    return true;
  });

  const tierCounts = useMemo(() => {
    const counts: Record<TierKey, number> = { top: 0, mid: 0, bot: 0 };
    for (const n of allNodes) counts[NODE_TYPE_TIER[n.node_type] ?? "mid"]++;
    return counts;
  }, [allNodes]);

  const toggleTier = (t: TierKey) => {
    setCollapsedTiers((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t); else next.add(t);
      return next;
    });
  };

  const visibleNodeIds = useMemo(() => new Set(filteredNodes.map((n: { id: number }) => n.id)), [filteredNodes]);

  // Counts (unfiltered, for legend) — validation nodes live on the Validations tab.
  const paymentNodes = allNodes.filter((n) => n.node_type !== "validation" && n.stream !== "validation");
  const inputNodes = paymentNodes.filter((n) => n.node_type === "input_value" || n.node_type === "input");
  const calcNodes = paymentNodes.filter((n) => n.node_type === "calculation");
  const distNodes = paymentNodes.filter((n) => n.node_type === "distribution");

  // Auto-layout: topological waterfall
  const autoLayout = () => {
    // Build adjacency
    const childrenOf: Record<number, number[]> = {};
    const parentCount: Record<number, number> = {};
    for (const n of allNodes) parentCount[n.id] = 0;
    for (const e of edges) {
      (childrenOf[e.source_node_id] ??= []).push(e.target_node_id);
      parentCount[e.target_node_id] = (parentCount[e.target_node_id] ?? 0) + 1;
    }
    // Topological sort by layers (BFS)
    const layers: number[][] = [];
    let current = allNodes.filter((n) => (parentCount[n.id] ?? 0) === 0).map((n) => n.id);
    const placed = new Set<number>();
    while (current.length > 0) {
      layers.push(current);
      for (const nid of current) placed.add(nid);
      const next: number[] = [];
      for (const nid of current) {
        for (const cid of (childrenOf[nid] ?? [])) {
          if (!placed.has(cid) && !next.includes(cid)) {
            // Check all parents are placed
            const allParentsPlaced = (edges.filter((e) => e.target_node_id === cid).every((e) => placed.has(e.source_node_id)));
            if (allParentsPlaced) next.push(cid);
          }
        }
      }
      current = next;
    }
    // Position: each layer is a row, nodes spread horizontally
    const nodeWidth = 240;
    const nodeHeight = 120;
    const xGap = 40;
    const yGap = 60;
    for (let layerIdx = 0; layerIdx < layers.length; layerIdx++) {
      const layer = layers[layerIdx];
      const totalWidth = layer.length * nodeWidth + (layer.length - 1) * xGap;
      const startX = Math.max(0, (800 - totalWidth) / 2);
      for (let i = 0; i < layer.length; i++) {
        const nid = layer[i];
        updateNodeMut.mutate({
          nodeId: nid,
          fields: {
            position_x: Math.round(startX + i * (nodeWidth + xGap)),
            position_y: Math.round(layerIdx * (nodeHeight + yGap)),
          },
        });
      }
    }
  };

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
      updateNode(nodeId, fields, id),
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

  const [newNodeName, setNewNodeName] = useState("");
  const [newNodeType, setNewNodeType] = useState("calculation");
  const [newFormula, setNewFormula] = useState("");
  const [newPaymentType, setNewPaymentType] = useState("");
  const [newVariableId, setNewVariableId] = useState<number | null>(null);
  // For input_value nodes: the source kind selected in the dialog.
  //   "tape"       → pick an existing mapped variable; node reads context by name.
  //   "static"     → store a literal number in `formula` (e.g. "2500").
  //   "expression" → store a small expression in `formula` (e.g.
  //                   "deal_trustee_fee_monthly").
  const [newInputSource, setNewInputSource] = useState<"tape" | "static" | "expression">("tape");
  const [newStaticValue, setNewStaticValue] = useState("");

  const slugify = (s: string): string =>
    s
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 80);

  // Ensure uniqueness against existing node keys (append _2, _3, ...).
  const uniqueKey = (base: string): string => {
    const taken = new Set(allNodes.map((n) => n.key));
    if (!taken.has(base)) return base;
    let i = 2;
    while (taken.has(`${base}_${i}`)) i++;
    return `${base}_${i}`;
  };

  const resetAddForm = () => {
    setNewNodeName("");
    setNewNodeType("calculation");
    setNewFormula("");
    setNewPaymentType("");
    setNewVariableId(null);
    setNewInputSource("tape");
    setNewStaticValue("");
  };

  const handleAddNode = () => {
    let key: string;
    let name: string;
    const payload: any = {
      node_type: newNodeType,
      stream: "distribution",
      position_x: 200 + Math.random() * 300,
      position_y: 100 + allNodes.length * 60,
    };

    if (newNodeType === "input_value") {
      if (newInputSource === "tape") {
        const v = mappedVariables.find((mv) => mv.id === newVariableId);
        if (!v) return;
        key = uniqueKey(slugify(v.name));
        name = v.display_name || v.name;
        payload.input_source = "tape";
        payload.variable_id = v.id;
        // No formula — executor reads context[v.name] directly.
      } else {
        // Static value or expression — both get stored in `formula` and
        // evaluated at execution time by the formula engine.
        if (!newNodeName.trim()) return;
        const base = slugify(newNodeName) || `input_${Date.now()}`;
        key = uniqueKey(base);
        name = newNodeName.trim();
        payload.input_source = newInputSource;
        if (newInputSource === "static") {
          const trimmed = newStaticValue.trim();
          if (!trimmed || !/^-?\d+(\.\d+)?$/.test(trimmed)) return;
          payload.formula = trimmed;
        } else {
          if (!newFormula.trim()) return;
          payload.formula = newFormula;
        }
      }
    } else {
      if (!newNodeName.trim()) return;
      const base = slugify(newNodeName) || `node_${Date.now()}`;
      key = uniqueKey(base);
      name = newNodeName.trim();
      if (newFormula) payload.formula = newFormula;
      if (newNodeType === "distribution" && newPaymentType) {
        // Write to both — `payment_type` drives the global export templates,
        // `export_field` drives the waterfall display. Keep them in sync.
        payload.payment_type = newPaymentType;
        payload.export_field = newPaymentType;
      }
    }

    payload.node_key = key;
    payload.name = name;

    createNodeMut.mutate(payload, {
      onSuccess: () => {
        setShowAddNode(false);
        resetAddForm();
      },
    });
  };

  // Node type colors
  const typeColor = (t: string) => {
    if (t === "input" || t === "input_value") return "#4ade80";
    if (t === "calculation") return "#60a5fa";
    if (t === "distribution") return "#a78bfa";
    if (t === "validation") return "#fbbf24";
    return "var(--text-muted)";
  };

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
        <Link to={`/deals/${dealId}`} style={{ color: "var(--accent-blue)", textDecoration: "none" }}>
          ← Back to deal
        </Link>
      </div>
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
        {isEditable && (
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn" onClick={() => setShowHistory(true)}>
              History
            </button>
            <label className="btn" style={{ cursor: "pointer", marginBottom: 0 }}>
              Import…
              <input
                type="file"
                accept="application/json,.json"
                style={{ display: "none" }}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  e.target.value = "";
                  if (!file) return;
                  try {
                    const text = await file.text();
                    const payload = JSON.parse(text);
                    await importDag(id, payload);
                    invalidate();
                  } catch (err) {
                    alert(`Import failed: ${(err as Error).message}`);
                  }
                }}
              />
            </label>
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

      {/* Toolbar */}
      <div className={styles.toggleRow}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button className={`btn ${viewMode === "table" ? "btn-primary" : ""}`} onClick={() => setViewMode("table")}>Table</button>
          <button className={`btn ${viewMode === "graph" ? "btn-primary" : ""}`} onClick={() => setViewMode("graph")}>Graph</button>
          {isEditable && (
            <button className="btn" onClick={() => setShowAddNode(true)}>+ Add node</button>
          )}
          <button className="btn" onClick={autoLayout} title="Auto-arrange nodes in waterfall layout">Auto-layout</button>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="input"
            placeholder="Search nodes..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            style={{ width: 180, padding: "5px 10px", fontSize: 12 }}
          />
          {focusNodeId && (
            <button className="btn btn-secondary btn-sm" onClick={() => setFocusNodeId(null)}>
              Show all
            </button>
          )}
        </div>
      </div>

      {/* Filter checkboxes + legend */}
      <div className={styles.legend} style={{ gap: 16 }}>
        {[
          { type: "input_value", label: "Input", color: "#4ade80", count: inputNodes.length },
          { type: "calculation", label: "Calculation", color: "#60a5fa", count: calcNodes.length },
          { type: "distribution", label: "Distribution", color: "#a78bfa", count: distNodes.length },
        ].map(({ type, label, color, count }) => (
          <label key={type} style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={typeFilters[type]}
              onChange={(e) => setTypeFilters((prev) => ({ ...prev, [type]: e.target.checked }))}
              style={{ accentColor: color }}
            />
            <span className={styles.dot} style={{ background: color }} />
            {label} ({count})
          </label>
        ))}
        <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
          Showing {filteredNodes.length} of {paymentNodes.length}
          {focusNodeId && " (focused)"}
        </span>
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
              <th></th>
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
                <td style={{ maxWidth: 300 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <code style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                      {node.formula ?? "—"}
                    </code>
                    {isEditable && node.node_type !== "input_value" && (
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ flexShrink: 0, fontSize: 11 }}
                        onClick={() => setEditingFormulaNode({
                          id: node.id,
                          node_type: node.node_type,
                          formula: node.formula ?? "",
                          comparison_variable: node.comparison_variable ?? null,
                          tolerance: node.tolerance != null ? String(node.tolerance) : null,
                        })}
                      >
                        Edit
                      </button>
                    )}
                  </div>
                </td>
                <td>
                  {node.payment_type && (
                    <span className={styles.exportBadge}>{node.payment_type}</span>
                  )}
                  {!node.payment_type && "—"}
                </td>
                <td>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button
                      className={styles.actionLink}
                      style={{ color: "var(--accent-blue)" }}
                      onClick={() => {
                        if (focusNodeId === node.id) {
                          setFocusNodeId(null);
                        } else {
                          setFocusNodeId(node.id);
                          setViewMode("graph");
                        }
                      }}
                    >
                      {focusNodeId === node.id ? "Unfocus" : "Focus"}
                    </button>
                    {isEditable && node.is_active && (
                      <button
                        className={styles.actionLink}
                        onClick={() => deactivateMut.mutate(node.id)}
                      >
                        Deactivate
                      </button>
                    )}
                    {isEditable && !node.is_active && (
                      <button
                        className={styles.actionLink}
                        style={{ color: "var(--accent-green)" }}
                        onClick={() => reactivateMut.mutate(node.id)}
                      >
                        Reactivate
                      </button>
                    )}
                    {isEditable && (
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
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ── Graph View ──────────────────────────────────────── */}
      {viewMode === "graph" && (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Tiers:
            </span>
            {([
              { key: "top" as TierKey, label: "Distribution & Validation", color: "#a78bfa" },
              { key: "mid" as TierKey, label: "Calculations", color: "#60a5fa" },
              { key: "bot" as TierKey, label: "Inputs", color: "#4ade80" },
            ]).map(({ key, label, color }) => {
              const collapsed = collapsedTiers.has(key);
              return (
                <button
                  key={key}
                  onClick={() => toggleTier(key)}
                  title={collapsed ? `Show ${label}` : `Hide ${label}`}
                  style={{
                    padding: "4px 10px",
                    fontSize: 11,
                    border: `1px solid ${color}`,
                    borderRadius: 999,
                    background: collapsed ? "transparent" : `${color}22`,
                    color: collapsed ? "var(--text-muted)" : color,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    opacity: collapsed ? 0.65 : 1,
                  }}
                >
                  <span>{collapsed ? "▶" : "▼"}</span>
                  {label} ({tierCounts[key]})
                </button>
              );
            })}
          </div>
          <DagGraphView
          backendNodes={allNodes}
          backendEdges={edges}
          visibleNodeIds={visibleNodeIds}
          availableTokens={availableTokens}
          mappedVariables={mappedVariables}
          onCreateNode={async (type, pos) => {
            const key = `new_${type}_${Date.now()}`;
            const resp = await createNode(id, {
              node_key: key,
              name: `New ${type}`,
              node_type: type,
              stream: type === "validation" ? "validation" : "distribution",
              position_x: pos.x,
              position_y: pos.y,
            } as any);
            invalidate();
            return resp;
          }}
          onUpdateNode={async (nodeId, fields) => {
            await updateNode(nodeId, fields, id);
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
        </>
      )}

      {/* ── Add Node Dialog ─────────────────────────────────── */}
      {showAddNode && (
        <div className={styles.overlay} onClick={() => setShowAddNode(false)}>
          <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.dialogTitle}>
              Add node
            </h2>

            <div className="form-row">
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Node type</label>
                <select
                  className="select"
                  style={{ width: "100%" }}
                  value={newNodeType}
                  onChange={(e) => setNewNodeType(e.target.value)}
                >
                  <option value="input_value">Input variable</option>
                  <option value="calculation">Calculation</option>
                  <option value="distribution">Distribution (export)</option>
                </select>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                  Validation checks are managed on the Validations tab.
                </div>
              </div>
            </div>

            {newNodeType === "input_value" && (
              <div className="form-group">
                <label className="form-label">Source</label>
                <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                  {([
                    { key: "tape", label: "Tape variable", hint: "Read from an extracted tape cell" },
                    { key: "static", label: "Static value", hint: "A literal number (e.g. 2500)" },
                    { key: "expression", label: "Expression", hint: "Derived from deal constants or other ambient values" },
                  ] as const).map((opt) => (
                    <button
                      key={opt.key}
                      type="button"
                      onClick={() => setNewInputSource(opt.key)}
                      style={{
                        flex: 1,
                        padding: "8px 10px",
                        fontSize: 12,
                        textAlign: "left",
                        background: newInputSource === opt.key ? "rgba(96,165,250,0.15)" : "var(--bg-secondary)",
                        border: `1px solid ${newInputSource === opt.key ? "var(--accent-blue)" : "var(--border-color)"}`,
                        borderRadius: 4,
                        color: "var(--text-primary)",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ fontWeight: 600, marginBottom: 2 }}>{opt.label}</div>
                      <div style={{ fontSize: 10, color: "var(--text-muted)" }}>{opt.hint}</div>
                    </button>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                  Note: any tape variable is already available to formulas by name —
                  you only need an Input node here for <em>non-tape</em> inputs
                  (static values, deal-constant overrides) or when you want
                  the value to appear as a node in the graph.
                </div>
              </div>
            )}

            {newNodeType === "input_value" && newInputSource === "tape" ? (
              <div className="form-group">
                <label className="form-label">Tape variable</label>
                <select
                  className="select"
                  style={{ width: "100%" }}
                  value={newVariableId ?? ""}
                  onChange={(e) => setNewVariableId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">— pick a mapped variable —</option>
                  {mappedVariables.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.display_name || v.name} ({v.name})
                    </option>
                  ))}
                </select>
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                  Only variables mapped on this deal are shown. The node key and display name are derived automatically.
                </div>
              </div>
            ) : (
              <div className="form-group">
                <label className="form-label">Display name</label>
                <input
                  className="input"
                  value={newNodeName}
                  onChange={(e) => setNewNodeName(e.target.value)}
                  placeholder="e.g. Class A Interest"
                />
                {newNodeName.trim() && (
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4, fontFamily: "var(--font-mono)" }}>
                    node_key: <span style={{ color: "var(--accent-blue)" }}>{uniqueKey(slugify(newNodeName))}</span>
                  </div>
                )}
              </div>
            )}

            {newNodeType === "input_value" && newInputSource === "static" && (
              <div className="form-group">
                <label className="form-label">Static value</label>
                <input
                  className="input"
                  inputMode="decimal"
                  value={newStaticValue}
                  onChange={(e) => setNewStaticValue(e.target.value.replace(/[^0-9.\-]/g, ""))}
                  placeholder="e.g. 2500"
                  style={{ fontFamily: "var(--font-mono)" }}
                />
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                  Stored as a literal in the node's formula. Useful for fixed fees or hand-entered thresholds not on the tape.
                </div>
              </div>
            )}

            {(newNodeType === "calculation" ||
              newNodeType === "distribution" ||
              (newNodeType === "input_value" && newInputSource === "expression")) && (
              <div className="form-group">
                <label className="form-label">Formula</label>
                <FormulaChipBuilder
                  value={newFormula}
                  onChange={setNewFormula}
                  tokens={availableTokens}
                  placeholder={
                    newInputSource === "expression"
                      ? "e.g. deal_trustee_fee_monthly"
                      : "e.g. class_a_balance * class_a_note_rate / 12"
                  }
                />
                <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                  Tip: <code>PRIOR(x)</code> returns last month's value of a variable or node — e.g.&nbsp;
                  <code>PRIOR(end_pool_balance_calc)</code> for this month's beginning pool balance.
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

            <div className={styles.dialogActions}>
              <button className="btn" onClick={() => { setShowAddNode(false); resetAddForm(); }}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleAddNode}
                disabled={
                  createNodeMut.isPending ||
                  (newNodeType === "input_value"
                    ? newInputSource === "tape"
                      ? !newVariableId
                      : newInputSource === "static"
                        ? !newStaticValue.trim() || !newNodeName.trim()
                        : !newFormula.trim() || !newNodeName.trim()
                    : !newNodeName.trim())
                }
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
                {v.id !== currentVersion?.id && isEditable && (
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

      {/* ── Formula Editor Modal (table view) ─────────────── */}
      {editingFormulaNode && (
        <FormulaEditorModal
          node={editingFormulaNode}
          tokens={availableTokens}
          mappedVariables={mappedVariables}
          onSave={(payload) => {
            const fields: Record<string, string | number | null | undefined> = {
              formula: payload.formula || null,
            };
            if (payload.comparison_variable !== undefined) {
              fields.comparison_variable = payload.comparison_variable;
            }
            if (payload.tolerance !== undefined) {
              fields.tolerance = payload.tolerance;
            }
            updateNodeMut.mutate({
              nodeId: editingFormulaNode.id,
              fields,
            });
            setEditingFormulaNode(null);
          }}
          onCancel={() => setEditingFormulaNode(null)}
        />
      )}
    </div>
  );
}