import { api } from "./client";

export interface WaterfallStep {
  step: number;
  node_key: string;
  node_name: string;
  amount: string;
  remaining_after: string;
  export_field: string | null;
  payment_type: string | null;
}

export interface WaterfallTrace {
  run_id: number;
  run_code: string;
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
}

export function getWaterfall(
  dealId: number,
  runId: number,
): Promise<WaterfallTrace> {
  return api.get<WaterfallTrace>(`/deals/${dealId}/runs/${runId}/waterfall`);
}

export interface WaterfallConfig {
  starting_var: string;
  ending_var: string;
  tolerance: string;
}

export function updateWaterfallConfig(
  dealId: number,
  payload: {
    waterfall_starting_var?: string;
    waterfall_ending_var?: string;
    waterfall_tolerance?: string;
  },
): Promise<WaterfallConfig> {
  return api.patch<WaterfallConfig>(
    `/deals/${dealId}/waterfall-config`,
    payload,
  );
}
