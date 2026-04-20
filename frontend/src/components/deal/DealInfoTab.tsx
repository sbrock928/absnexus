import { useEffect, useState } from "react";
import { api } from "../../api/client";
import {
  type DealAccount,
  type PeriodPreview,
  createDealAccount,
  deleteDealAccount,
  fetchDealAccounts,
  fetchPeriodPreview,
  updateDealAccount,
} from "../../api/dealAccounts";
import type { Deal } from "../../types";
import { useToast } from "../Toast";

interface Props {
  deal: Deal;
  onDealChanged: (deal: Deal) => void;
  readOnly?: boolean;
}

type StaticField =
  | "issuer_name"
  | "deal_key"
  | "closing_date"
  | "initial_cutoff_date"
  | "initial_distribution_date"
  | "cutoff_pool_balance"
  | "distribution_day_of_month"
  | "determination_business_days_before"
  | "servicing_fee_pct"
  | "backup_servicing_fee_pct"
  | "trustee_fee_monthly"
  | "target_oc_pct"
  | "target_oc_floor_pct"
  | "target_oc_floor_amount"
  | "reserve_required_pct";

const CONSTANTS: Array<{
  field: StaticField;
  label: string;
  placeholder: string;
  varName: string;
}> = [
  { field: "servicing_fee_pct", label: "Monthly servicing fee %", placeholder: "0.04", varName: "deal_servicing_fee_pct" },
  { field: "backup_servicing_fee_pct", label: "Backup servicing fee %", placeholder: "0.00015", varName: "deal_backup_servicing_fee_pct" },
  { field: "trustee_fee_monthly", label: "Monthly trustee fee ($)", placeholder: "750.00", varName: "deal_trustee_fee_monthly" },
  { field: "target_oc_pct", label: "Target OC %", placeholder: "0.2230", varName: "deal_target_oc_pct" },
  { field: "target_oc_floor_pct", label: "Target OC floor %", placeholder: "0.025", varName: "deal_target_oc_floor_pct" },
  { field: "target_oc_floor_amount", label: "Target OC floor amount ($)", placeholder: "16250072.66", varName: "deal_target_oc_floor_amount" },
  { field: "reserve_required_pct", label: "Reserve required %", placeholder: "0.01", varName: "deal_reserve_required_pct" },
];

function todayPeriod(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function DealInfoTab({ deal, onDealChanged, readOnly = false }: Props) {
  const { toast } = useToast();
  const [accounts, setAccounts] = useState<DealAccount[]>([]);
  const [newLabel, setNewLabel] = useState("");
  const [newNumber, setNewNumber] = useState("");
  const [previewPeriod, setPreviewPeriod] = useState(todayPeriod());
  const [preview, setPreview] = useState<PeriodPreview | null>(null);

  useEffect(() => {
    fetchDealAccounts(deal.id).then(setAccounts).catch(() => setAccounts([]));
  }, [deal.id]);

  useEffect(() => {
    fetchPeriodPreview(deal.id, previewPeriod)
      .then(setPreview)
      .catch(() => setPreview(null));
  }, [deal.id, previewPeriod, deal.distribution_day_of_month, deal.determination_business_days_before, deal.initial_cutoff_date]);

  async function saveField(field: StaticField, value: string | number | null) {
    try {
      const updated = await api.patch<Deal>(`/deals/${deal.id}`, { [field]: value });
      onDealChanged(updated);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Save failed", "error");
    }
  }

  async function saveBool(field: "reg_ab" | "equity_cusips_involved", value: boolean) {
    try {
      const updated = await api.patch<Deal>(`/deals/${deal.id}`, { [field]: value });
      onDealChanged(updated);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Save failed", "error");
    }
  }

  async function handleAddAccount() {
    if (!newLabel.trim() || !newNumber.trim()) return;
    try {
      const created = await createDealAccount(deal.id, {
        label: newLabel.trim(),
        account_number: newNumber.trim(),
        position: accounts.length + 1,
      });
      setAccounts([...accounts, created]);
      setNewLabel("");
      setNewNumber("");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to add account", "error");
    }
  }

  async function handleUpdateAccount(id: number, body: Partial<DealAccount>) {
    try {
      const updated = await updateDealAccount(deal.id, id, body);
      setAccounts(accounts.map((a) => (a.id === id ? updated : a)));
    } catch (e) {
      toast(e instanceof Error ? e.message : "Update failed", "error");
    }
  }

  async function handleDeleteAccount(id: number) {
    try {
      await deleteDealAccount(deal.id, id);
      setAccounts(accounts.filter((a) => a.id !== id));
    } catch (e) {
      toast(e instanceof Error ? e.message : "Delete failed", "error");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* ── Static deal info ── */}
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Deal information</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Field label="Issuer">
            <input
              className="input"
              value={deal.issuer_name ?? ""}
              disabled={readOnly}
              onChange={(e) => onDealChanged({ ...deal, issuer_name: e.target.value })}
              onBlur={(e) => saveField("issuer_name", e.target.value || null)}
              placeholder="American Credit Acceptance Receivables Trust 2025-4"
            />
          </Field>
          <Field label="Deal key">
            <input
              className="input"
              value={deal.deal_key ?? ""}
              disabled={readOnly}
              onChange={(e) => onDealChanged({ ...deal, deal_key: e.target.value })}
              onBlur={(e) => saveField("deal_key", e.target.value || null)}
              placeholder="ACA254"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </Field>
          <Field label="REG AB?">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={deal.reg_ab ?? false}
                disabled={readOnly}
                onChange={(e) => saveBool("reg_ab", e.target.checked)}
              />
              <span style={{ color: "var(--text-muted)", fontSize: 13 }}>Yes</span>
            </label>
          </Field>
          <Field label="Equity CUSIPs involved?">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={deal.equity_cusips_involved ?? false}
                disabled={readOnly}
                onChange={(e) => saveBool("equity_cusips_involved", e.target.checked)}
              />
              <span style={{ color: "var(--text-muted)", fontSize: 13 }}>Yes</span>
            </label>
          </Field>
          <Field label="Closing date">
            <input
              type="date"
              className="input"
              value={deal.closing_date ?? ""}
              disabled={readOnly}
              onChange={(e) => onDealChanged({ ...deal, closing_date: e.target.value })}
              onBlur={(e) => saveField("closing_date", e.target.value || null)}
            />
          </Field>
          <Field label="Initial cutoff date">
            <input
              type="date"
              className="input"
              value={deal.initial_cutoff_date ?? ""}
              disabled={readOnly}
              onChange={(e) => onDealChanged({ ...deal, initial_cutoff_date: e.target.value })}
              onBlur={(e) => saveField("initial_cutoff_date", e.target.value || null)}
            />
          </Field>
          <Field label="Initial distribution date">
            <input
              type="date"
              className="input"
              value={deal.initial_distribution_date ?? ""}
              disabled={readOnly}
              onChange={(e) => onDealChanged({ ...deal, initial_distribution_date: e.target.value })}
              onBlur={(e) => saveField("initial_distribution_date", e.target.value || null)}
            />
          </Field>
          <Field label="Cutoff date pool balance ($)">
            <input
              className="input"
              value={deal.cutoff_pool_balance ?? ""}
              disabled={readOnly}
              onChange={(e) => onDealChanged({ ...deal, cutoff_pool_balance: e.target.value })}
              onBlur={(e) => saveField("cutoff_pool_balance", e.target.value || null)}
              placeholder="455000312.51"
              style={{ fontFamily: "var(--font-mono)" }}
            />
          </Field>
          <Field label="Distribution day-of-month">
            <input
              type="number"
              min={1}
              max={31}
              className="input"
              value={deal.distribution_day_of_month ?? ""}
              disabled={readOnly}
              onChange={(e) =>
                onDealChanged({
                  ...deal,
                  distribution_day_of_month: e.target.value ? Number(e.target.value) : null,
                })
              }
              onBlur={(e) =>
                saveField("distribution_day_of_month", e.target.value ? Number(e.target.value) : null)
              }
              placeholder="12"
            />
            <HelpText>e.g. 12 → bumped to next Mon–Fri if it falls on a weekend.</HelpText>
          </Field>
          <Field label="Determination: business days before distribution">
            <input
              type="number"
              min={0}
              max={30}
              className="input"
              value={deal.determination_business_days_before ?? ""}
              disabled={readOnly}
              onChange={(e) =>
                onDealChanged({
                  ...deal,
                  determination_business_days_before: e.target.value ? Number(e.target.value) : null,
                })
              }
              onBlur={(e) =>
                saveField(
                  "determination_business_days_before",
                  e.target.value ? Number(e.target.value) : null,
                )
              }
              placeholder="4"
            />
          </Field>
        </div>
      </div>

      {/* ── Period preview ── */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontWeight: 600 }}>Computed period dates</div>
          <label style={{ fontSize: 12, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 6 }}>
            Preview period
            <input
              type="month"
              className="input"
              value={previewPeriod}
              onChange={(e) => setPreviewPeriod(e.target.value)}
              style={{ padding: "4px 8px" }}
            />
          </label>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
          <PreviewCell label="Distribution date" value={preview?.distribution_date} />
          <PreviewCell label="Determination date" value={preview?.determination_date} />
          <PreviewCell
            label="Days in period (calendar)"
            value={preview?.days_in_period_actual?.toString() ?? null}
          />
          <PreviewCell
            label="Days in period (30/360)"
            value={preview?.days_in_period_30_360?.toString() ?? null}
          />
        </div>

        {/* Explicit day-count breakdown: how the 30/360 number is derived */}
        <div
          style={{
            marginTop: 12,
            padding: 12,
            background: "var(--bg-tertiary)",
            borderRadius: 6,
            fontSize: 12,
            fontFamily: "var(--font-mono)",
            color: "var(--text-secondary)",
            lineHeight: 1.6,
          }}
        >
          <div style={{ color: "var(--text-muted)", marginBottom: 4, fontFamily: "inherit" }}>
            How the 30/360 day count is derived:
          </div>
          <div>
            anchor (<span style={{ color: "var(--accent-blue)" }}>{anchorSourceLabel(preview?.anchor_source)}</span>)
            = <span style={{ color: "var(--text-primary)" }}>{preview?.anchor_date ?? "—"}</span>
          </div>
          <div>
            distribution date = <span style={{ color: "var(--text-primary)" }}>{preview?.distribution_date ?? "—"}</span>
          </div>
          <div>
            days_30_360(anchor, distribution) ={" "}
            <span style={{ color: "var(--accent-green)", fontWeight: 600 }}>
              {preview?.days_in_period_30_360 ?? "—"}
            </span>
          </div>
        </div>

        <HelpText>
          These values are auto-injected into DAG formulas as <code>period_days_in_period_actual</code>,{" "}
          <code>period_days_in_period_30_360</code>, <code>deal_cutoff_pool_balance</code>, etc. The
          30/360 day count is validated against the tape's <code>days_of_interest_reported</code> variable
          (cell E19 on Servicer B's certificate) via the <code>days_of_interest_check</code> validation.
        </HelpText>
      </div>

      {/* ── Deal-level numeric constants ── */}
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 4 }}>Deal constants</div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
          Fee rates, OC thresholds, and reserve requirements. Each field is injected into DAG formulas as a reserved variable name so nodes can reference it directly.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {CONSTANTS.map(({ field, label, placeholder, varName }) => (
            <Field key={field} label={label}>
              <input
                className="input"
                value={(deal[field] as string | number | null | undefined) ?? ""}
                disabled={readOnly}
                onChange={(e) => onDealChanged({ ...deal, [field]: e.target.value })}
                onBlur={(e) => saveField(field, e.target.value || null)}
                placeholder={placeholder}
                style={{ fontFamily: "var(--font-mono)" }}
              />
              <HelpText>
                Formula name: <code>{varName}</code>
              </HelpText>
            </Field>
          ))}
        </div>
      </div>

      {/* ── Trust accounts ── */}
      <div className="card">
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Trust accounts</div>
        {accounts.length === 0 ? (
          <div style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 12 }}>
            No accounts yet.
          </div>
        ) : (
          <table className="table" style={{ marginBottom: 12 }}>
            <thead>
              <tr>
                <th style={{ width: 60 }}>#</th>
                <th>Label</th>
                <th>Account number</th>
                <th style={{ width: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                    {a.position}
                  </td>
                  <td>
                    <input
                      className="input"
                      defaultValue={a.label}
                      disabled={readOnly}
                      onBlur={(e) => {
                        if (e.target.value !== a.label) handleUpdateAccount(a.id, { label: e.target.value });
                      }}
                    />
                  </td>
                  <td>
                    <input
                      className="input"
                      defaultValue={a.account_number}
                      disabled={readOnly}
                      onBlur={(e) => {
                        if (e.target.value !== a.account_number)
                          handleUpdateAccount(a.id, { account_number: e.target.value });
                      }}
                      style={{ fontFamily: "var(--font-mono)" }}
                    />
                  </td>
                  <td>
                    {!readOnly && (
                      <button
                        className="btn btn-sm btn-ghost"
                        onClick={() => handleDeleteAccount(a.id)}
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!readOnly && (
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              className="input"
              placeholder="Label (e.g. Main Account)"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              style={{ flex: 1 }}
            />
            <input
              className="input"
              placeholder="Account number"
              value={newNumber}
              onChange={(e) => setNewNumber(e.target.value)}
              style={{ flex: 1, fontFamily: "var(--font-mono)" }}
            />
            <button className="btn btn-primary" onClick={handleAddAccount}>
              + Add account
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginBottom: 4 }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function HelpText({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>{children}</div>;
}

function anchorSourceLabel(source: string | null | undefined): string {
  switch (source) {
    case "prior_run":
      return "prior run's distribution";
    case "prior_month_computed":
      return "previous month (computed)";
    case "initial_cutoff":
      return "deal initial cutoff";
    default:
      return "—";
  }
}

function PreviewCell({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.4 }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, fontFamily: "var(--font-mono)", marginTop: 4 }}>
        {value ?? "—"}
      </div>
    </div>
  );
}
