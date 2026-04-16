import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { CellMapper } from "../components/cell-mapper/CellMapper";
import type { Deal } from "../types";

export function CellMapperPage() {
  const { dealId } = useParams<{ dealId: string }>();
  const id = Number(dealId);
  const navigate = useNavigate();

  const { data: deal } = useQuery({
    queryKey: ["deal", id],
    queryFn: () => api.get<Deal>(`/deals/${id}`),
  });

  // Check if any processing run has a tape uploaded
  const { data: runs = [] } = useQuery({
    queryKey: ["deal-runs", id],
    queryFn: () => api.get<any[]>(`/deals/${id}/runs`),
  });
  const hasTape = runs.some((r: any) => r.tape_file_path);

  if (!deal) {
    return (
      <div>
        <div className="page-header">
          <div>
            <div className="page-title">Cell mapper</div>
            <div className="page-subtitle">Loading...</div>
          </div>
        </div>
      </div>
    );
  }

  if (!hasTape) {
    return (
      <div>
        <div className="page-header">
          <div>
            <div className="page-title">Cell mapper — {deal.name}</div>
            <div className="page-subtitle">No tape uploaded yet</div>
          </div>
          <button className="btn btn-secondary" onClick={() => navigate(`/deals/${id}`)}>
            Back to deal
          </button>
        </div>
        <div
          style={{
            padding: 32,
            textAlign: "center",
            background: "var(--bg-card)",
            border: "1px dashed var(--border)",
            borderRadius: 8,
          }}
        >
          <div style={{ marginBottom: 12, color: "var(--text-muted)" }}>
            Upload a servicer tape through the processing workflow first, then come back here to
            map cells to variables.
          </div>
          <button className="btn btn-primary" onClick={() => navigate("/processing")}>
            Go to processing
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Map servicer tape to variables</div>
          <div className="page-subtitle">
            Click any cell, then bind it to a variable. Green cells are already mapped.
          </div>
        </div>
        <button className="btn btn-secondary" onClick={() => navigate(`/deals/${id}`)}>
          Back to deal
        </button>
      </div>

      <CellMapper dealId={id} />
    </div>
  );
}
