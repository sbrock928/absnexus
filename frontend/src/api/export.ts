import { api } from "./client";

/* ── Types ─────────────────────────────────────────────────── */

export interface ExportColumn {
  id: number;
  deal_id: number;
  position: number;
  header_label: string;
  value_type: "distribution_node" | "literal" | "run_meta" | "deal_meta";
  node_id: number | null;
  literal_value: string | null;
  meta_field: string | null;
  format_type: string;
  decimal_places: number | null;
  prorate_by: string | null;
  prorate_class_label: string | null;
}

export interface PresetInfo {
  key: string;
  name: string;
  description: string;
  column_count: number;
}

export interface PreviewResponse {
  csv: string;
  row_count: number;
}

/* ── Columns CRUD ──────────────────────────────────────────── */

export function listColumns(dealId: number): Promise<ExportColumn[]> {
  return api.get<ExportColumn[]>(`/deals/${dealId}/export-columns`);
}

export function createColumn(
  dealId: number,
  payload: Partial<ExportColumn>,
): Promise<ExportColumn> {
  return api.post<ExportColumn>(`/deals/${dealId}/export-columns`, payload);
}

export function updateColumn(
  columnId: number,
  fields: Partial<ExportColumn>,
): Promise<ExportColumn> {
  return api.patch<ExportColumn>(`/export-columns/${columnId}`, fields);
}

export function deleteColumn(columnId: number): Promise<void> {
  return api.del(`/export-columns/${columnId}`) as Promise<void>;
}

export function reorderColumns(
  dealId: number,
  orderedIds: number[],
): Promise<ExportColumn[]> {
  return api.post<ExportColumn[]>(`/deals/${dealId}/export-columns/reorder`, {
    ordered_column_ids: orderedIds,
  });
}

export function copyPreset(
  dealId: number,
  presetKey: string,
): Promise<ExportColumn[]> {
  return api.post<ExportColumn[]>(`/deals/${dealId}/export-columns/copy-preset`, {
    preset_key: presetKey,
  });
}

/* ── Presets + preview ─────────────────────────────────────── */

export function listPresets(): Promise<PresetInfo[]> {
  return api.get<PresetInfo[]>("/export-presets");
}

export function previewExport(
  dealId: number,
  runId?: number,
): Promise<PreviewResponse> {
  const params = runId ? `?run_id=${runId}` : "";
  return api.get<PreviewResponse>(`/deals/${dealId}/export-preview${params}`);
}
