import { api } from "./client";

/* ── Types ─────────────────────────────────────────────────── */

export interface DagNode {
  id: number;
  key: string;
  name: string;
  node_type: string;
  stream: string;
  formula: string | null;
  description: string | null;
  input_source: string | null;
  variable_id: number | null;
  payment_type: string | null;
  export_field: string | null;
  tolerance: number | null;
  tolerance_type: string | null;
  comparison_variable: string | null;
  default_prior_value: number | null;
  waterfall_order: number | null;
  position_x: number;
  position_y: number;
  is_active: boolean;
}

export interface DagEdge {
  id: number;
  source_node_id: number;
  target_node_id: number;
}

export interface DagVersion {
  id: number;
  deal_id: number;
  version_number: number;
  description: string | null;
  created_by: string;
  created_at: string;
  is_current: boolean;
}

/* ── DAG load (returns current snapshot) ───────────────────── */

interface DagLoadResponse {
  version: DagVersion;
  nodes: DagNode[];
  edges: DagEdge[];
}

/* ── Queries ───────────────────────────────────────────────── */

export async function fetchNodes(dealId: number): Promise<DagNode[]> {
  const res = await api.get<DagLoadResponse>(`/deals/${dealId}/dag`);
  return res.nodes;
}

export async function fetchEdges(dealId: number): Promise<DagEdge[]> {
  const res = await api.get<DagLoadResponse>(`/deals/${dealId}/dag`);
  return res.edges;
}

export async function fetchVersions(dealId: number): Promise<DagVersion[]> {
  return api.get<DagVersion[]>(`/deals/${dealId}/dag/versions`);
}

/* ── Node mutations ────────────────────────────────────────── */

export function createNode(dealId: number, payload: Partial<DagNode>): Promise<DagNode> {
  return api.post<DagNode>(`/deals/${dealId}/dag/nodes`, payload);
}

export function updateNode(nodeId: number, fields: Record<string, unknown>, dealId?: number): Promise<DagNode> {
  if (dealId) {
    return api.patch<DagNode>(`/deals/${dealId}/dag/nodes/${nodeId}`, fields);
  }
  return api.patch<DagNode>(`/dag/nodes/${nodeId}`, fields);
}

export function deleteNode(nodeId: number): Promise<void> {
  return api.del(`/dag/nodes/${nodeId}`) as Promise<void>;
}

export function deactivateNode(nodeId: number): Promise<void> {
  return api.patch<void>(`/dag/nodes/${nodeId}/deactivate`, {});
}

export function reactivateNode(nodeId: number): Promise<void> {
  return api.patch<void>(`/dag/nodes/${nodeId}/reactivate`, {});
}

/* ── Edge mutations ────────────────────────────────────────── */

export function createEdge(
  dealId: number,
  payload: { source_node_id: number; target_node_id: number },
): Promise<DagEdge> {
  return api.post<DagEdge>(`/deals/${dealId}/dag/edges`, payload);
}

export function deleteEdge(edgeId: number): Promise<void> {
  return api.del(`/dag/edges/${edgeId}`) as Promise<void>;
}

/* ── Version mutations ─────────────────────────────────────── */

export function saveDag(
  dealId: number,
  description: string,
): Promise<{ version_id: number; version_number: number }> {
  return api.post(`/deals/${dealId}/dag`, { description });
}

export function revertDag(
  dealId: number,
  versionId: number,
): Promise<{ version_id: number; version_number: number }> {
  return api.post(`/deals/${dealId}/dag/revert/${versionId}`);
}

export function importDag(
  dealId: number,
  payload: Record<string, unknown>,
): Promise<{ version_id: number; version_number: number }> {
  return api.post(`/deals/${dealId}/dag/import`, payload);
}
