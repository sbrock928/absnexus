import { useQuery } from "@tanstack/react-query";
import { getWaterfall, getWaterfallPdfUrl } from "../../api/waterfall";
import styles from "./WaterfallTrace.module.css";

function formatMoney(val: string | null): string {
  if (val === null) return "—";
  const num = parseFloat(val);
  if (isNaN(num)) return val;
  return num.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

interface Props {
  dealId: number;
  runId: number;
  onContinue?: () => void;
  onInvestigate?: () => void;
}

export function WaterfallTrace({ dealId, runId, onContinue, onInvestigate }: Props) {
  const {
    data: wf,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["waterfall", runId],
    queryFn: () => getWaterfall(dealId, runId),
  });

  if (isLoading) return <div className={styles.loading}>Loading waterfall...</div>;
  if (error || !wf) {
    return (
      <div className={styles.errorBox}>
        Unable to compute waterfall. The deal may be missing a mapping for the
        starting or ending variable.
      </div>
    );
  }

  const passed = wf.reconciled === true;
  const failed = wf.reconciled === false;
  const noTape = !wf.has_tape_value;
  const hasComparisons = wf.comparison_count > 0;

  return (
    <div>
      {/* Starting balance card */}
      <div className={styles.startCard}>
        <div className={styles.startLabel}>
          Starting balance (<code>{wf.starting_var}</code>)
        </div>
        <div className={styles.startValue}>
          {formatMoney(wf.starting_balance)}
        </div>
      </div>

      {/* ── Distribution Comparison Table ── */}
      {hasComparisons && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, marginTop: 16 }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>
              Distribution Comparison
              <span style={{ fontWeight: 400, fontSize: 12, color: "var(--text-muted)", marginLeft: 8 }}>
                {wf.comparison_matched} of {wf.comparison_count} matched
              </span>
            </div>
            <a
              href={getWaterfallPdfUrl(dealId, runId)}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-secondary btn-sm"
              style={{ textDecoration: "none" }}
            >
              Export PDF
            </a>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>#</th>
                <th>Distribution</th>
                <th style={{ textAlign: "right" }}>Our Calculation</th>
                <th style={{ textAlign: "right" }}>Tape Value</th>
                <th style={{ textAlign: "right" }}>Difference</th>
                <th style={{ textAlign: "center", width: 80 }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {wf.steps.filter((s) => s.tape_value !== null).map((s) => (
                <tr key={s.step}>
                  <td style={{ color: "var(--text-muted)" }}>{s.step}</td>
                  <td>
                    <span style={{ fontWeight: 500 }}>{s.node_name}</span>
                    {s.export_field && (
                      <span className={styles.fieldCode}>{s.export_field}</span>
                    )}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                    {formatMoney(s.amount)}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                    {formatMoney(s.tape_value)}
                  </td>
                  <td style={{
                    textAlign: "right",
                    fontFamily: "var(--font-mono)",
                    color: s.matched === false ? "var(--accent-red)" : "var(--text-muted)",
                  }}>
                    {formatMoney(s.difference)}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    {s.matched === true && (
                      <span className="badge" style={{ background: "rgba(74,222,128,0.15)", color: "var(--accent-green)" }}>MATCH</span>
                    )}
                    {s.matched === false && (
                      <span className="badge" style={{ background: "rgba(248,113,113,0.15)", color: "var(--accent-red)" }}>MISMATCH</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* ── Balance Waterfall Table ── */}
      <div style={{ fontWeight: 600, fontSize: 14, marginTop: 16, marginBottom: 8 }}>Balance Waterfall</div>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: 40 }}>#</th>
            <th>Distribution</th>
            <th style={{ textAlign: "right" }}>Amount</th>
            <th style={{ textAlign: "right" }}>Remaining</th>
          </tr>
        </thead>
        <tbody>
          {wf.steps.map((s) => (
            <tr key={s.step}>
              <td style={{ color: "var(--text-muted)" }}>{s.step}</td>
              <td>
                <span style={{ fontWeight: 500 }}>{s.node_name}</span>
                {s.export_field && (
                  <span className={styles.fieldCode}>{s.export_field}</span>
                )}
              </td>
              <td
                style={{
                  textAlign: "right",
                  color: "var(--accent-red)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                - {formatMoney(s.amount)}
              </td>
              <td
                style={{
                  textAlign: "right",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                }}
              >
                {formatMoney(s.remaining_after)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Reconciliation card */}
      <div
        className={
          passed
            ? styles.reconPass
            : failed
              ? styles.reconFail
              : styles.reconInfo
        }
      >
        <div className={styles.reconRow}>
          <span>Final calculated remainder</span>
          <span className={styles.reconValue}>
            {formatMoney(wf.final_calculated_remainder)}
          </span>
        </div>

        {wf.has_tape_value && (
          <>
            <div className={styles.reconRow}>
              <span>
                Tape reported remainder (<code>{wf.ending_var}</code>)
              </span>
              <span className={styles.reconValue}>
                {formatMoney(wf.tape_ending_balance)}
              </span>
            </div>
            <div className={styles.reconRow}>
              <span>Difference</span>
              <span
                className={styles.reconValue}
                style={failed ? { color: "var(--accent-red)" } : undefined}
              >
                {formatMoney(wf.difference)}
              </span>
            </div>
            <div className={styles.reconRow}>
              <span>Tolerance</span>
              <span className={styles.reconValue}>
                +/- {formatMoney(wf.tolerance)}
              </span>
            </div>
          </>
        )}

        <div className={styles.reconStatus}>
          {passed && <span className={styles.passBadge}>RECONCILED</span>}
          {failed && <span className={styles.failBadge}>FAILED</span>}
          {noTape && (
            <span className={styles.infoBadge}>
              No tape ending value configured — add a mapping for{" "}
              <code>{wf.ending_var}</code> to enable reconciliation
            </span>
          )}
        </div>

        {failed && (
          <div className={styles.failExplanation}>
            <strong>Export blocked.</strong> The sum of distributions does not
            match what the tape expects to remain. Review each distribution
            amount above to find the discrepancy.
          </div>
        )}
      </div>

      {/* Actions */}
      <div className={styles.actions}>
        {!hasComparisons && (
          <a
            href={getWaterfallPdfUrl(dealId, runId)}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
            style={{ textDecoration: "none" }}
          >
            Export PDF
          </a>
        )}
        {failed && onInvestigate && (
          <button className="btn" onClick={onInvestigate}>
            Investigate trace
          </button>
        )}
        {(passed || noTape) && onContinue && (
          <button className="btn btn-primary" onClick={onContinue}>
            Continue to export
          </button>
        )}
      </div>
    </div>
  );
}
