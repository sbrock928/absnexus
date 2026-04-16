export interface DagNodeData {
  label: string;
  node_key: string;
  node_type: string;
  stream: string;
  is_active: boolean;
  formula?: string;
  input_source?: string;
  cell_ref?: string;
  export_field?: string;
  tolerance?: string;
  tolerance_type?: string;
  description?: string;
  variable_id?: number;
  default_prior_value?: string;
  comparison_variable?: string;
  payment_type?: string;
  backendId: number;
}
