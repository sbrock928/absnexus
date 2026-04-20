import dagre from "@dagrejs/dagre";

/**
 * Run dagre top-down layout over a set of React-Flow-shaped nodes/edges.
 * Returns a Map<nodeId, {x, y}> of centered positions.
 *
 * The DAG's natural ranking handles layering: input_value nodes end up at
 * the top (no incoming edges), then calculations, then distributions, then
 * validations at the bottom. No explicit tier constraints are needed.
 */
export interface NodeForLayout {
  id: string;
  node_type?: string;
}

export interface EdgeForLayout {
  source: string;
  target: string;
}

export interface LayoutOptions {
  direction?: "TB" | "LR";
  nodeWidth?: number;
  nodeHeight?: number;
  // horizontal space between nodes in the same rank
  nodeSep?: number;
  // vertical space between ranks
  rankSep?: number;
}

const DEFAULT_W = 240;
const DEFAULT_H = 110;

export function layoutDag(
  nodes: NodeForLayout[],
  edges: EdgeForLayout[],
  opts: LayoutOptions = {},
): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph({ multigraph: false, compound: false });
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: opts.direction ?? "TB",
    nodesep: opts.nodeSep ?? 70,
    ranksep: opts.rankSep ?? 120,
    marginx: 40,
    marginy: 40,
  });

  const w = opts.nodeWidth ?? DEFAULT_W;
  const h = opts.nodeHeight ?? DEFAULT_H;
  for (const n of nodes) {
    g.setNode(n.id, { width: w, height: h });
  }
  for (const e of edges) {
    // only add edges where both endpoints are present — prevents dagre errors
    // when a subset of nodes is being laid out (e.g. filtered lineage views).
    if (g.hasNode(e.source) && g.hasNode(e.target)) {
      g.setEdge(e.source, e.target);
    }
  }

  dagre.layout(g);

  const result = new Map<string, { x: number; y: number }>();
  for (const n of nodes) {
    const node = g.node(n.id);
    if (node) {
      // dagre centers nodes; React Flow expects top-left origin
      result.set(n.id, { x: node.x - w / 2, y: node.y - h / 2 });
    }
  }
  return result;
}
