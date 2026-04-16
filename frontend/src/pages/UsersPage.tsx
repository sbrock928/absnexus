import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchUsers, createUser, updateUser } from "../api/users";
import type { User } from "../types";
import styles from "./UsersPage.module.css";

const ROLES = ["analyst", "analytics", "admin"];

export function UsersPage() {
  const queryClient = useQueryClient();

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: fetchUsers,
  });

  // Add user form state
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [newRole, setNewRole] = useState("analyst");
  const [formError, setFormError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setUsername("");
      setDisplayName("");
      setNewRole("analyst");
      setFormError(null);
    },
    onError: (err: Error) => setFormError(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, body }: { userId: number; body: { role?: string; is_active?: boolean } }) =>
      updateUser(userId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !displayName.trim()) {
      setFormError("Username and display name are required.");
      return;
    }
    createMutation.mutate({ username: username.trim(), display_name: displayName.trim(), role: newRole });
  }

  function handleRoleChange(user: User, role: string) {
    updateMutation.mutate({ userId: user.id, body: { role } });
  }

  function handleToggleActive(user: User) {
    updateMutation.mutate({ userId: user.id, body: { is_active: !user.is_active } });
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Users</div>
          <div className="page-subtitle">{users.length} registered users</div>
        </div>
      </div>

      <form className={styles.addForm} onSubmit={handleAdd}>
        <div className={styles.fieldGroup}>
          <span className={styles.fieldLabel}>Username</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="windows.username"
            style={{ width: 180 }}
          />
        </div>
        <div className={styles.fieldGroup}>
          <span className={styles.fieldLabel}>Display name</span>
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Jane Chen"
            style={{ width: 180 }}
          />
        </div>
        <div className={styles.fieldGroup}>
          <span className={styles.fieldLabel}>Role</span>
          <select value={newRole} onChange={(e) => setNewRole(e.target.value)} style={{ width: 130 }}>
            {ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span className={styles.fieldLabel}>&nbsp;</span>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? "Adding..." : "Add user"}
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
      ) : users.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">No users yet</div>
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Display name</th>
              <th>Role</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className={u.is_active ? undefined : styles.inactiveRow}>
                <td style={{ fontFamily: "monospace", fontSize: 12 }}>{u.username}</td>
                <td>{u.display_name}</td>
                <td>
                  <select
                    className={styles.inlineSelect}
                    value={u.role}
                    onChange={(e) => handleRoleChange(u, e.target.value)}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <span
                    className="badge"
                    style={
                      u.is_active
                        ? { background: "rgba(74,222,128,0.15)", color: "var(--accent-green)" }
                        : { background: "rgba(147,148,160,0.15)", color: "var(--text-muted)" }
                    }
                  >
                    {u.is_active ? "active" : "inactive"}
                  </span>
                </td>
                <td>
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={() => handleToggleActive(u)}
                  >
                    {u.is_active ? "Deactivate" : "Reactivate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
