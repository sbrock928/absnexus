import { api } from "./client";

/* ── Types ── */

export interface Mapping {
  id: number;
  deal_id: number;
  variable_id: number;
  variable: { id: number; name: string; display_name: string | null } | null;
  sheet_name: string;
  column_letter: string;
  row_number: number;
  tape_label: string | null;
  created_at: string;
  updated_at: string;
}

export interface TapeGridRow {
  row_number: number;
  cells: Array<string | number | null>;
}

export interface TapeGridSheet {
  sheet_name: string;
  column_letters: string[];
  rows: TapeGridRow[];
}

export interface TapeGridResponse {
  filename: string;
  sheet_names: string[];
  sheet?: TapeGridSheet;
  sheets?: TapeGridSheet[];
}

/* ── API calls ── */

export function fetchMappings(dealId: number): Promise<Mapping[]> {
  return api.get<Mapping[]>(`/deals/${dealId}/mappings`);
}

export function createMapping(
  dealId: number,
  body: { variable_id: number; sheet_name: string; column_letter: string; row_number: number },
): Promise<Mapping> {
  return api.post<Mapping>(`/deals/${dealId}/mappings`, body);
}

export function updateMapping(
  dealId: number,
  mappingId: number,
  body: { sheet_name?: string; column_letter?: string; row_number?: number },
): Promise<Mapping> {
  return api.patch<Mapping>(`/deals/${dealId}/mappings/${mappingId}`, body);
}

export function deleteMapping(dealId: number, mappingId: number): Promise<void> {
  return api.del(`/deals/${dealId}/mappings/${mappingId}`) as Promise<void>;
}

export function fetchTapeGrid(dealId: number, runId?: number): Promise<TapeGridResponse> {
  const qs = runId ? `?run_id=${runId}` : "";
  return api.get<TapeGridResponse>(`/deals/${dealId}/tape-grid${qs}`);
}

export function fetchTapeSheet(
  dealId: number,
  sheetName: string,
): Promise<TapeGridResponse> {
  return api.get<TapeGridResponse>(
    `/deals/${dealId}/tape-grid?sheet=${encodeURIComponent(sheetName)}`,
  );
}

export function reextractVariable(
  dealId: number,
  runId: number,
  variableId: number,
): Promise<{
  variable_id: number;
  variable: string;
  cell: string;
  sheet: string;
  raw: string | null;
  parsed: string | null;
  prior: string | null;
  pct_change: string | null;
  warning: string | null;
}> {
  return api.post(`/deals/${dealId}/runs/${runId}/reextract-variable/${variableId}`);
}
