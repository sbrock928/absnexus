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

// ── Deal export row config ──

export interface DealExportCell {
  id: number;
  column_id: number;
  value_source: string;
  source_ref: string;
}

export interface DealExportRow {
  id: number;
  node_id: number;
  node_key: string | null;
  node_name: string | null;
  row_order: number;
  identifier_group: number | null;
  cells: DealExportCell[];
}

export interface DealExportConfig {
  rows: DealExportRow[];
}

export interface DealExportCellSave {
  column_id: number;
  value_source: string;
  source_ref: string;
}

export interface DealExportRowSave {
  node_id: number;
  row_order: number;
  identifier_group?: number | null;
  cells: DealExportCellSave[];
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

// ── Deal export config ──

export function getDealExportConfig(
  dealId: number,
  templateId: number,
): Promise<DealExportConfig> {
  return api.get<DealExportConfig>(`/deals/${dealId}/export-config/${templateId}`);
}

export function saveDealExportConfig(
  dealId: number,
  templateId: number,
  rows: DealExportRowSave[],
): Promise<DealExportConfig> {
  return api.put<DealExportConfig>(`/deals/${dealId}/export-config/${templateId}`, {
    rows,
  });
}

// ── Preview ──

export interface ExportPreview {
  columns: string[];
  rows: string[][];
}

export function getExportPreview(dealId: number, templateId: number): Promise<ExportPreview> {
  return api.get<ExportPreview>(`/deals/${dealId}/export-preview/${templateId}`);
}

export function getExportPreviewXlsxUrl(dealId: number, templateId: number): string {
  return `/api/deals/${dealId}/export-preview/${templateId}/xlsx`;
}
