import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { createBatch, executeBatch, type DealInputPayload } from "../api/batch";
import type { Deal, Servicer } from "../types";
import styles from "./BatchProcessingPage.module.css";

interface UploadResult {
  filename: string;
  file_path: string;
  file_hash: string;
}

interface DealTape {
  deal: Deal;
  file: File | null;
  uploadResult: UploadResult | null;
  uploading: boolean;
  error: string | null;
}

export function BatchProcessingPage() {
  const navigate = useNavigate();

  const [period, setPeriod] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  });

  const [deals, setDeals] = useState<Deal[]>([]);
  const [servicers, setServicers] = useState<Servicer[]>([]);
  const [dealTapes, setDealTapes] = useState<Record<number, DealTape>>({});
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchError, setBatchError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Deal[]>("/deals/"),
      api.get<Servicer[]>("/servicers/"),
    ]).then(([d, s]) => {
      setDeals(d);
      setServicers(s);
    });
  }, []);

  const activeDeals = deals.filter((d) => d.status === "active");
  const svcName = (id: number) =>
    servicers.find((s) => s.id === id)?.name ?? `Servicer #${id}`;

  // Initialize dealTapes when deals load
  useEffect(() => {
    if (activeDeals.length > 0 && Object.keys(dealTapes).length === 0) {
      const initial: Record<number, DealTape> = {};
      for (const d of activeDeals) {
        initial[d.id] = {
          deal: d,
          file: null,
          uploadResult: null,
          uploading: false,
          error: null,
        };
      }
      setDealTapes(initial);
    }
  }, [activeDeals.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFile = async (dealId: number, file: File) => {
    setDealTapes((prev) => ({
      ...prev,
      [dealId]: { ...prev[dealId], file, uploading: true, error: null },
    }));

    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/batches/upload-tape/${dealId}`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error("Upload failed");
      const result: UploadResult = await res.json();
      setDealTapes((prev) => ({
        ...prev,
        [dealId]: {
          ...prev[dealId],
          uploadResult: result,
          uploading: false,
        },
      }));
    } catch {
      setDealTapes((prev) => ({
        ...prev,
        [dealId]: {
          ...prev[dealId],
          uploading: false,
          error: "Upload failed",
        },
      }));
    }
  };

  const clearTapes = () => {
    const cleared: Record<number, DealTape> = {};
    for (const d of activeDeals) {
      cleared[d.id] = {
        deal: d,
        file: null,
        uploadResult: null,
        uploading: false,
        error: null,
      };
    }
    setDealTapes(cleared);
  };

  const readyDeals = Object.values(dealTapes).filter((dt) => dt.uploadResult);

  const startBatch = async () => {
    setBatchRunning(true);
    setBatchError("");
    try {
      const inputs: DealInputPayload[] = readyDeals.map((dt) => ({
        deal_id: dt.deal.id,
        source_filename: dt.uploadResult!.filename,
        source_file_path: dt.uploadResult!.file_path,
        source_file_hash: dt.uploadResult!.file_hash,
      }));
      const batch = await createBatch(period, inputs);
      await executeBatch(batch.id);
      navigate(`/batches/${batch.id}`);
    } catch (e: any) {
      setBatchError(e.message || "Batch execution failed.");
      setBatchRunning(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Monthly batch processing</div>
          <div className="page-subtitle">
            Run all active deals for the period in one click
          </div>
        </div>
        <button className="btn" onClick={() => navigate("/batches")}>
          History
        </button>
      </div>

      {/* Period + stats */}
      <div className={styles.statsRow}>
        <div className="form-group" style={{ margin: 0 }}>
          <label className="form-label">Report period</label>
          <input
            className="input"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            style={{ fontFamily: "var(--font-mono)", width: 140 }}
          />
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Active deals</div>
          <div className={styles.statValue}>{activeDeals.length}</div>
        </div>
        <div className={styles.stat}>
          <div className={styles.statLabel}>Tapes ready</div>
          <div className={styles.statValue}>
            {readyDeals.length} of {activeDeals.length}
          </div>
        </div>
      </div>

      {/* Deal list */}
      <table className="table" style={{ marginTop: 20 }}>
        <thead>
          <tr>
            <th>Deal</th>
            <th>Servicer</th>
            <th>Tape</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {activeDeals.map((d) => {
            const dt = dealTapes[d.id];
            if (!dt) return null;
            return (
              <tr key={d.id}>
                <td style={{ fontWeight: 500 }}>{d.name}</td>
                <td>{svcName(d.servicer_id)}</td>
                <td>
                  {dt.uploadResult ? (
                    <span
                      style={{
                        color: "var(--text-secondary)",
                        fontSize: 12,
                        fontFamily: "var(--font-mono)",
                      }}
                    >
                      {dt.uploadResult.filename}
                    </span>
                  ) : (
                    <>
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        id={`tape-${d.id}`}
                        style={{ display: "none" }}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) handleFile(d.id, f);
                        }}
                      />
                      <label
                        htmlFor={`tape-${d.id}`}
                        className={styles.uploadLabel}
                      >
                        {dt.uploading ? "Uploading..." : "Upload tape..."}
                      </label>
                    </>
                  )}
                </td>
                <td>
                  {dt.uploadResult && (
                    <span className="badge badge-green">✓ Ready</span>
                  )}
                  {dt.uploading && (
                    <span
                      style={{
                        fontSize: 12,
                        color: "var(--text-muted)",
                      }}
                    >
                      Uploading...
                    </span>
                  )}
                  {dt.error && (
                    <span className="badge badge-red">{dt.error}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Actions */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginTop: 20,
          justifyContent: "flex-end",
        }}
      >
        <button
          className="btn"
          onClick={clearTapes}
          disabled={readyDeals.length === 0 || batchRunning}
        >
          Clear tapes
        </button>
        <button
          className="btn btn-primary"
          onClick={startBatch}
          disabled={readyDeals.length === 0 || batchRunning}
        >
          {batchRunning
            ? "Running batch..."
            : `Start batch (${readyDeals.length} deal${readyDeals.length !== 1 ? "s" : ""})`}
        </button>
      </div>

      {batchError && (
        <div className="banner banner-warn" style={{ marginTop: 12 }}>
          {batchError}
        </div>
      )}
    </div>
  );
}
