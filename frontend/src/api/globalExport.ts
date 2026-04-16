import { api } from "./client";

export interface GlobalTemplate {
  id: number;
  name: string;
  description: string | null;
}

export interface GlobalColumn {
  id: number;
  template_id: number;
  position: number;
  header_label: string;
  value_type: "distribution_node" | "literal" | "run_meta" | "deal_meta";
  literal_value: string | null;
  meta_field: string | null;
  format_type: string;
  decimal_places: number | null;
  prorate_by: string | null;
  prorate_class_label: string | null;
}

export interface TemplateWithColumns {
  template: GlobalTemplate;
  columns: GlobalColumn[];
}

export interface DealMapping {
  id: number;
  column_id: number;
  node_id: number;
  header_label: string | null;
  node_key: string | null;
  node_name: string | null;
}

// ── Templates ──

export function listTemplates(): Promise<GlobalTemplate[]> {
  return api.get<GlobalTemplate[]>("/export-templates");
}

export function getTemplate(templateId: number): Promise<TemplateWithColumns> {
  return api.get<TemplateWithColumns>(`/export-templates/${templateId}`);
}

// ── Columns ──

export function createColumn(
  templateId: number,
  body: Partial<GlobalColumn>,
): Promise<GlobalColumn> {
  return api.post<GlobalColumn>(`/export-templates/${templateId}/columns`, body);
}

export function updateGlobalColumn(
  columnId: number,
  body: Partial<GlobalColumn>,
): Promise<GlobalColumn> {
  return api.patch<GlobalColumn>(`/global-export-columns/${columnId}`, body);
}

export function deleteGlobalColumn(columnId: number): Promise<void> {
  return api.del(`/global-export-columns/${columnId}`) as Promise<void>;
}

export function reorderGlobalColumns(
  templateId: number,
  orderedIds: number[],
): Promise<GlobalColumn[]> {
  return api.post<GlobalColumn[]>(`/export-templates/${templateId}/columns/reorder`, {
    ordered_column_ids: orderedIds,
  });
}

// ── Deal mappings ──

export function getDealMappings(
  dealId: number,
  templateId: number,
): Promise<DealMapping[]> {
  return api.get<DealMapping[]>(`/deals/${dealId}/export-mappings/${templateId}`);
}

export function saveDealMappings(
  dealId: number,
  templateId: number,
  mappings: Array<{ column_id: number; node_id: number }>,
): Promise<DealMapping[]> {
  return api.put<DealMapping[]>(`/deals/${dealId}/export-mappings/${templateId}`, {
    mappings,
  });
}
