import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBatchSummary, getBatchZipUrl } from "../api/batch";
import styles from "./BatchResultsPage.module.css";

function formatMoney(val: string): string {
  const num = parseFloat(val);
  if (isNaN(num)) return val;
  return num.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  });
}

export function BatchResultsPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const id = Number(batchId);
  const navigate = useNavigate();

  const { data: summary, isLoading } = useQuery({
    queryKey: ["batch-summary", id],
    queryFn: () => getBatchSummary(id),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 2000;
      if (data.status === "running" || data.status === "pending") return 2000;
      return false;
    },
  });

  if (isLoading || !summary) return <div>Loading batch...</div>;

  const isRunning =
    summary.status === "running" || summary.status === "pending";
  const isFullSuccess = summary.status === "completed";
  const isPartial = summary.status === "completed_with_errors";

  return (
    <div>
      <div className={styles.breadcrumb}>Deals / Monthly batch run</div>

      <div className="page-header">
        <div>
          <div className="page-title">
            Monthly processing — {summary.report_period}
          </div>
          <div
            className="page-subtitle"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {summary.batch_code}
          </div>
        </div>
        {!isRunning && summary.exports_ready > 0 && (
          <a href={getBatchZipUrl(id)} className="btn btn-primary" download>
            Export all CSVs (zip)
          </a>
        )}
      </div>

      {/* Status banner */}
      <div
        className={
          isFullSuccess
            ? styles.bannerSuccess
            : isPartial
              ? styles.bannerPartial
              : isRunning
                ? styles.bannerRunning
                : styles.bannerError
        }
      >
        {isRunning && (
          <>
            Running batch... {summary.deals_completed + summary.deals_failed} of{" "}
            {summary.deals_total} deals processed
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{
                  width: `${
                    ((summary.deals_completed + summary.deals_failed) /
                      summary.deals_total) *
                    100
                  }%`,
                }}
              />
            </div>
          </>
        )}
        {!isRunning && (
          <div style={{ display: "flex", gap: 16 }}>
            <span>● {summary.deals_completed} passed</span>
            {summary.deals_failed > 0 && (
              <span>● {summary.deals_failed} failed</span>
            )}
            <span style={{ color: "var(--text-muted)" }}>
              ·{" "}
              {summary.execution_time_ms
                ? `${(summary.execution_time_ms / 1000).toFixed(1)}s`
                : "—"}
            </span>
          </div>
        )}
      </div>

      {/* Stats grid */}
      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Deals processed</div>
          <div className={styles.statValue}>{summary.deals_total}</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Total nodes executed</div>
          <div className={styles.statValue}>{summary.total_nodes}</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Total distributions</div>
          <div className={styles.statValue}>
            {formatMoney(summary.total_distribution)}
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Validations passed</div>
          <div className={styles.statValue}>
            {summary.validations_passed} /{" "}
            {summary.validations_passed + summary.validations_failed}
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Exports ready</div>
          <div className={styles.statValue}>
            {summary.exports_ready} / {summary.deals_total}
          </div>
        </div>
      </div>

      {/* Per-deal cards */}
      {summary.deals.map((d) => {
        const passed = d.status === "completed";
        const failed = d.status === "failed";
        const running =
          d.status === "running" ||
          d.status === "pending" ||
          d.status === "extracted";

        return (
          <div
            key={d.run_id}
            className={failed ? styles.dealCardFail : styles.dealCard}
          >
            <div className={styles.dealHeader}>
              <div>
                <div className={styles.dealName}>{d.deal_name}</div>
                <div className={styles.dealMeta}>{d.run_code}</div>
              </div>
              <div className={styles.dealStats}>
                <div>{d.nodes_executed} nodes</div>
                {d.execution_time_ms !== null && (
                  <div>{(d.execution_time_ms / 1000).toFixed(1)}s</div>
                )}
                <div>{formatMoney(d.total_distribution)}</div>
                {passed && (
                  <span className="badge badge-green">Passed</span>
                )}
                {failed && <span className="badge badge-red">Failed</span>}
                {running && (
                  <span className="badge badge-yellow">Running</span>
                )}
              </div>
            </div>

            {/* Distribution outputs + validations side by side */}
            {(d.distributions.length > 0 || d.validations.length > 0) && (
              <div className={styles.dealBody}>
                {d.distributions.length > 0 && (
                  <div>
                    <div className={styles.subTitle}>Distribution outputs</div>
                    <div className={styles.dualList}>
                      {d.distributions.map((dist, i) => (
                        <div key={i} className={styles.dualRow}>
                          <span className={styles.fieldCode}>
                            {dist.field_code || dist.payment_type}
                          </span>
                          <span>{formatMoney(dist.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {d.validations.length > 0 && (
                  <div>
                    <div className={styles.subTitle}>Validation checks</div>
                    <div className={styles.dualList}>
                      {d.validations.map((v) => (
                        <div key={v.node_key} className={styles.dualRow}>
                          <span style={{ fontSize: 12 }}>{v.node_name}</span>
                          {v.passed ? (
                            <span className="badge badge-green">Pass</span>
                          ) : (
                            <span className="badge badge-red">Fail</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Failure investigation link */}
            {d.first_failed_validation && (
              <div className={styles.failInvestigate}>
                <span style={{ color: "var(--accent-red)" }}>
                  ⚠ {d.first_failed_validation.node_name} failed — diff{" "}
                  {formatMoney(d.first_failed_validation.difference)}
                </span>
                <button
                  className={styles.investigateLink}
                  onClick={() =>
                    navigate(
                      `/deals/${d.deal_id}/runs/${d.run_id}/lineage/${d.first_failed_validation!.node_key}`,
                    )
                  }
                >
                  Investigate →
                </button>
              </div>
            )}

            {/* Trace link for completed runs */}
            {passed && (
              <div style={{ marginTop: 8 }}>
                <button
                  className={styles.traceLink}
                  onClick={() =>
                    navigate(
                      `/deals/${d.deal_id}/runs/${d.run_id}/trace`,
                    )
                  }
                >
                  View full trace →
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
