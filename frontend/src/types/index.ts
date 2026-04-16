export interface User {
  id: number;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
}

export interface Servicer {
  id: number;
  name: string;
  short_code: string;
}

export interface Deal {
  id: number;
  name: string;
  servicer_id: number;
  product_type: string;
  status: string;
  cloned_from_id: number | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Variable {
  id: number;
  name: string;
  display_name: string | null;
  data_type: string;
  scope: string;
  servicer_id: number | null;
  deal_id: number | null;
  description: string | null;
}

export interface DagNode {
  id: number;
  key: string;
  name: string;
  node_type: "input_value" | "calculation" | "distribution" | "validation";
  stream: "distribution" | "validation";
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

export interface AuditLogEntry {
  id: number;
  user_id: number;
  user_display_name: string;
  entity_type: string;
  entity_id: number;
  action: string;
  changes: Record<string, unknown> | null;
  description: string | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}
