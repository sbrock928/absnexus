import { api } from "./client";

export interface DealAccount {
  id: number;
  deal_id: number;
  label: string;
  account_number: string;
  position: number;
  created_at: string;
}

export interface PeriodPreview {
  report_period: string;
  distribution_date: string | null;
  determination_date: string | null;
  days_in_period_actual: number | null;
  days_in_period_30_360: number | null;
  anchor_date: string | null;
  anchor_source: string | null; // "prior_run" | "prior_month_computed" | "initial_cutoff"
}

export function fetchDealAccounts(dealId: number): Promise<DealAccount[]> {
  return api.get<DealAccount[]>(`/deals/${dealId}/accounts`);
}

export function createDealAccount(
  dealId: number,
  body: { label: string; account_number: string; position?: number },
): Promise<DealAccount> {
  return api.post<DealAccount>(`/deals/${dealId}/accounts`, body);
}

export function updateDealAccount(
  dealId: number,
  accountId: number,
  body: { label?: string; account_number?: string; position?: number },
): Promise<DealAccount> {
  return api.patch<DealAccount>(`/deals/${dealId}/accounts/${accountId}`, body);
}

export function deleteDealAccount(dealId: number, accountId: number): Promise<void> {
  return api.del(`/deals/${dealId}/accounts/${accountId}`) as Promise<void>;
}

export function fetchPeriodPreview(
  dealId: number,
  period: string,
): Promise<PeriodPreview> {
  return api.get<PeriodPreview>(
    `/deals/${dealId}/period-preview?period=${encodeURIComponent(period)}`,
  );
}
