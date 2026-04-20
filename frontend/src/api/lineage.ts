import { api } from "./client";

export interface LineageNode {
  node_key: string;
  node_name: string;
  node_type: string;
  stream: string;
  execution_order: number | null;
  formula: string | null;
  formula_resolved: string | null;
  result: string | null;
  prior_value: string | null;
  delta_pct: string | null;
  is_suspect: boolean;
  suspect_reason: string | null;
  upstream_keys: string[];
  comparison_value: string | null;
  difference: string | null;
  tolerance: string | null;
  validation_passed: boolean | null;
  input_source: string | null;
  cell_ref: string | null;
}

export interface LineageResponse {
  target_node_key: string;
  target_node_name: string;
  target_node_type: string;
  target_result: string | null;
  lineage_count: number;
  nodes: LineageNode[];
}

export function getLineage(
  dealId: number,
  runId: number,
  nodeKey: string,
): Promise<LineageResponse> {
  return api.get<LineageResponse>(
    `/deals/${dealId}/runs/${runId}/lineage/${nodeKey}`,
  );
}
