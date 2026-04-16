import { api } from "./client";

/* ── Types ─────────────────────────────────────────────────── */

export interface BatchRun {
  id: number;
  batch_code: string;
  report_period: string;
  status: string;
  deals_total: number;
  deals_completed: number;
  deals_failed: number;
  started_by: string;
  started_at: string | null;
  completed_at: string | null;
  execution_time_ms: number | null;
  created_at: string;
}

export interface DealInputPayload {
  deal_id: number;
  source_filename: string;
  source_file_path: string;
  source_file_hash: string;
}

export interface BatchDealSummary {
  run_id: number;
  run_code: string;
  deal_id: number;
  deal_name: string;
  status: string;
  nodes_executed: number;
  execution_time_ms: number | null;
  total_distribution: string;
  validations_passed: number;
  validations_failed: number;
  has_export: boolean;
  distributions: Array<{
    field_code: string;
    payment_type: string;
    amount: string;
  }>;
  validations: Array<{
    node_key: string;
    node_name: string;
    passed: boolean;
    difference: string;
  }>;
  first_failed_validation: {
    node_key: string;
    node_name: string;
    difference: string;
  } | null;
}

export interface BatchSummary {
  batch_id: number;
  batch_code: string;
  report_period: string;
  status: string;
  deals_total: number;
  deals_completed: number;
  deals_failed: number;
  total_distribution: string;
  total_nodes: number;
  validations_passed: number;
  validations_failed: number;
  exports_ready: number;
  execution_time_ms: number | null;
  started_by: string;
  started_at: string | null;
  completed_at: string | null;
  deals: BatchDealSummary[];
}

/* ── API calls ─────────────────────────────────────────────── */

export function listBatches(limit = 20): Promise<BatchRun[]> {
  return api.get<BatchRun[]>(`/batches?limit=${limit}`);
}

export function getBatch(batchId: number): Promise<BatchRun> {
  return api.get<BatchRun>(`/batches/${batchId}`);
}

export function getBatchSummary(batchId: number): Promise<BatchSummary> {
  return api.get<BatchSummary>(`/batches/${batchId}/summary`);
}

export function createBatch(
  reportPeriod: string,
  dealInputs: DealInputPayload[],
): Promise<BatchRun> {
  return api.post<BatchRun>(`/batches`, {
    report_period: reportPeriod,
    deal_inputs: dealInputs,
  });
}

export function executeBatch(batchId: number): Promise<BatchRun> {
  return api.post<BatchRun>(`/batches/${batchId}/execute`);
}

export function getBatchZipUrl(batchId: number): string {
  return `/api/batches/${batchId}/zip`;
}
