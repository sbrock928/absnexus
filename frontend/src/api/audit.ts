import { api } from "./client";
import type { AuditLogListResponse } from "../types";

export interface AuditFilters {
  entity_type?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export function fetchAuditLogs(
  filters: AuditFilters,
): Promise<AuditLogListResponse> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== "") params.set(k, String(v));
  }
  const qs = params.toString();
  return api.get<AuditLogListResponse>(`/audit/${qs ? `?${qs}` : ""}`);
}
