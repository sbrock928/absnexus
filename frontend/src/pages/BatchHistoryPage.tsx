import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listBatches } from "../api/batch";

export function BatchHistoryPage() {
  const navigate = useNavigate();
  const { data: batches = [] } = useQuery({
    queryKey: ["batches"],
    queryFn: () => listBatches(50),
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Batch history</div>
          <div className="page-subtitle">{batches.length} batch runs</div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate("/batch")}>
          Start new batch
        </button>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Batch code</th>
            <th>Period</th>
            <th>Status</th>
            <th>Deals</th>
            <th>Time</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {batches.map((b) => (
            <tr
              key={b.id}
              onClick={() => navigate(`/batches/${b.id}`)}
              style={{ cursor: "pointer" }}
            >
              <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                {b.batch_code}
              </td>
              <td>{b.report_period}</td>
              <td>
                <span
                  className={`badge ${
                    b.status === "completed"
                      ? "badge-green"
                      : b.status === "completed_with_errors"
                        ? "badge-yellow"
                        : b.status === "failed"
                          ? "badge-red"
                          : "badge-blue"
                  }`}
                >
                  {b.status}
                </span>
              </td>
              <td>
                {b.deals_completed}/{b.deals_total}
                {b.deals_failed > 0 && (
                  <span
                    style={{ color: "var(--accent-red)", marginLeft: 6 }}
                  >
                    ({b.deals_failed} failed)
                  </span>
                )}
              </td>
              <td style={{ fontSize: 12 }}>
                {b.execution_time_ms
                  ? `${(b.execution_time_ms / 1000).toFixed(1)}s`
                  : "—"}
              </td>
              <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                {b.started_at
                  ? new Date(b.started_at).toLocaleString()
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
