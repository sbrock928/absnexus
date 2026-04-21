import { api } from "./client";

export interface WaterfallStep {
  step: number;
  node_key: string;
  node_name: string;
  amount: string;
  remaining_after: string;
  export_field: string | null;
  payment_type: string | null;
  comparison_value: string | null;
  difference: string | null;
  matched: boolean | null;
  comparison_variable: string | null;
  comparison_data_type: string | null;
  tape_variable: string | null;
  tape_data_type: string | null;
}

export interface WaterfallTrace {
  run_id: number;
  run_code: string;
  deal_name: string;
  report_period: string;
  starting_var: string;
  starting_balance: string;
  ending_var: string;
  tape_ending_balance: string | null;
  tolerance: string;
  steps: WaterfallStep[];
  step_count: number;
  final_calculated_remainder: string;
  difference: string | null;
  reconciled: boolean | null;
  has_tape_value: boolean;
  comparison_count: number;
  comparison_matched: number;
  all_compared: boolean;
}

export function getWaterfall(
  dealId: number,
  runId: number,
): Promise<WaterfallTrace> {
  return api.get<WaterfallTrace>(`/deals/${dealId}/runs/${runId}/waterfall`);
}

export function getWaterfallPdfUrl(dealId: number, runId: number): string {
  return `/api/deals/${dealId}/runs/${runId}/waterfall/pdf`;
}
