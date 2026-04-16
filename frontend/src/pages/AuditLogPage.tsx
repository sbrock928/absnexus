import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { fetchAuditLogs, type AuditFilters } from "../api/audit";
import type { AuditLogEntry } from "../types";
import styles from "./AuditLogPage.module.css";

const ENTITY_TYPES = [
  { value: "", label: "All entities" },
  { value: "deal", label: "Deal" },
  { value: "dag_node", label: "DAG node" },
  { value: "dag_version", label: "DAG version" },
  { value: "variable_mapping", label: "Variable mapping" },
  { value: "tranche", label: "Tranche" },
  { value: "variable_alias", label: "Variable alias" },
  { value: "variable", label: "Variable" },
];

const ACTIONS = [
  { value: "", label: "All actions" },
  { value: "create", label: "Created" },
  { value: "update", label: "Updated" },
  { value: "delete", label: "Deleted" },
  { value: "deactivate", label: "Deactivated" },
  { value: "revert", label: "Reverted" },
  { value: "clone", label: "Cloned" },
];

const PAGE_SIZE = 50;

function actionBadgeClass(action: string): string {
  switch (action) {
    case "create":
    case "clone":
      return styles.badgeCreate;
    case "update":
    case "revert":
      return styles.badgeUpdate;
    case "delete":
    case "deactivate":
      return styles.badgeDelete;
    default:
      return styles.badgeDefault;
  }
}

function formatChanges(changes: Record<string, unknown>): string {
  return JSON.stringify(changes, null, 2);
}

export function AuditLogPage() {
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set());

  const filters: AuditFilters = {
    page,
    page_size: PAGE_SIZE,
    ...(entityType && { entity_type: entityType }),
    ...(action && { action }),
    ...(dateFrom && { date_from: dateFrom }),
    ...(dateTo && { date_to: dateTo }),
  };

  const { data, isLoading } = useQuery({
    queryKey: ["audit", filters],
    queryFn: () => fetchAuditLogs(filters),
    placeholderData: keepPreviousData,
  });

  const totalPages = data ? Math.ceil(data.total / data.page_size) || 1 : 1;

  function resetPage() {
    setPage(1);
  }

  function toggleExpanded(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function renderRow(entry: AuditLogEntry) {
    const isOpen = expanded.has(entry.id);
    return (
      <tr key={entry.id}>
        <td style={{ fontSize: 12, color: "var(--text-muted)", whiteSpace: "nowrap" }}>
          {new Date(entry.created_at).toLocaleString()}
        </td>
        <td>{entry.user_display_name}</td>
        <td>
          <span className={styles.entityTag}>{entry.entity_type}</span>
          <span style={{ marginLeft: 6, fontFamily: "monospace", fontSize: 12 }}>
            #{entry.entity_id}
          </span>
        </td>
        <td>
          <span className={`badge ${actionBadgeClass(entry.action)}`}>
            {entry.action}
          </span>
        </td>
        <td>
          {entry.description && (
            <span style={{ fontSize: 13 }}>{entry.description}</span>
          )}
          {entry.changes && (
            <div>
              <button
                className={styles.toggleBtn}
                onClick={() => toggleExpanded(entry.id)}
              >
                {isOpen ? "Hide diff" : "Show diff"}
              </button>
              {isOpen && (
                <pre className={styles.diffPre}>
                  {formatChanges(entry.changes)}
                </pre>
              )}
            </div>
          )}
        </td>
      </tr>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Audit log</div>
          <div className="page-subtitle">
            {data ? `${data.total} entries` : "Loading..."}
          </div>
        </div>
      </div>

      <div className={styles.filterBar}>
        <select
          value={entityType}
          onChange={(e) => { setEntityType(e.target.value); resetPage(); }}
        >
          {ENTITY_TYPES.map((et) => (
            <option key={et.value} value={et.value}>{et.label}</option>
          ))}
        </select>

        <select
          value={action}
          onChange={(e) => { setAction(e.target.value); resetPage(); }}
        >
          {ACTIONS.map((a) => (
            <option key={a.value} value={a.value}>{a.label}</option>
          ))}
        </select>

        <input
          type="date"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); resetPage(); }}
          title="From date"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); resetPage(); }}
          title="To date"
        />

        {(entityType || action || dateFrom || dateTo) && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setEntityType("");
              setAction("");
              setDateFrom("");
              setDateTo("");
              resetPage();
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading && !data ? (
        <p style={{ color: "var(--text-muted)" }}>Loading...</p>
      ) : data && data.items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No audit entries found</div>
          <div className="empty-state-text">
            {entityType || action || dateFrom || dateTo
              ? "Try adjusting your filters."
              : "Activity will appear here as changes are made."}
          </div>
        </div>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>User</th>
                <th>Entity</th>
                <th>Action</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>{data?.items.map(renderRow)}</tbody>
          </table>

          {totalPages > 1 && (
            <div className={styles.pagination}>
              <button
                className="btn btn-secondary btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span>
                Page {data?.page ?? page} of {totalPages}
              </span>
              <button
                className="btn btn-secondary btn-sm"
                disabled={!data?.has_more}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
