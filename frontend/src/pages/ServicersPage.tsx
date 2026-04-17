import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useToast } from "../components/Toast";
import { fetchServicers, createServicer } from "../api/servicers";
import styles from "./UsersPage.module.css";

export function ServicersPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: servicers = [], isLoading } = useQuery({
    queryKey: ["servicers"],
    queryFn: fetchServicers,
  });

  const [name, setName] = useState("");
  const [shortCode, setShortCode] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: createServicer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["servicers"] });
      setName("");
      setShortCode("");
      setFormError(null);
      toast("Servicer created");
    },
    onError: (err: Error) => {
      setFormError(err.message);
      toast(err.message, "error");
    },
  });

  function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !shortCode.trim()) {
      setFormError("Name and short code are required.");
      return;
    }
    createMutation.mutate({ name: name.trim(), short_code: shortCode.trim().toUpperCase() });
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Servicers</div>
          <div className="page-subtitle">{servicers.length} servicers</div>
        </div>
      </div>

      <form className={styles.addForm} onSubmit={handleAdd}>
        <div className={styles.fieldGroup}>
          <span className={styles.fieldLabel}>Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Servicer Name"
            style={{ width: 220 }}
          />
        </div>
        <div className={styles.fieldGroup}>
          <span className={styles.fieldLabel}>Short code</span>
          <input
            value={shortCode}
            onChange={(e) => setShortCode(e.target.value)}
            placeholder="ABC"
            style={{ width: 100 }}
            maxLength={10}
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span className={styles.fieldLabel}>&nbsp;</span>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? "Adding..." : "Add servicer"}
          </button>
        </div>
        {formError && (
          <p style={{ color: "var(--accent-red)", fontSize: 13, width: "100%" }}>
            {formError}
          </p>
        )}
      </form>

      {isLoading ? (
        <p style={{ color: "var(--text-muted)" }}>Loading...</p>
      ) : servicers.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No servicers yet</div>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Short code</th>
            </tr>
          </thead>
          <tbody>
            {servicers.map((s) => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td style={{ fontFamily: "monospace", fontSize: 12 }}>{s.short_code}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
