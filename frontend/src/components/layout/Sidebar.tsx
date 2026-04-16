import { NavLink } from "react-router-dom";
import { useAuth } from "../../auth";

function SidebarLink({ to, label }: { to: string; label: string }) {
  return (
    <NavLink to={to} className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
      {label}
    </NavLink>
  );
}

export function Sidebar() {
  const { user, isModeler, isAdmin } = useAuth();

  return (
    <div className="sidebar">
      <div className="sidebar-brand">ABSNexus</div>
      <nav>
        {isModeler ? (
          <>
            <div className="sidebar-section">Deal Setup</div>
            <SidebarLink to="/deals" label="Deals" />
            <SidebarLink to="/variables" label="Variables" />
            <SidebarLink to="/variable-map" label="Variable Map" />
            <SidebarLink to="/export-templates" label="Export Templates" />

            <div className="sidebar-section">Monthly Processing</div>
            <SidebarLink to="/processing" label="Processing" />
            <SidebarLink to="/batch" label="Batch" />

            <div className="sidebar-section">Admin</div>
            <SidebarLink to="/audit" label="Audit Log" />
            {isAdmin && <SidebarLink to="/users" label="Users" />}
          </>
        ) : (
          <>
            <div className="sidebar-section">Processing</div>
            <SidebarLink to="/deals" label="Deals" />
            <SidebarLink to="/processing" label="Processing" />
            <SidebarLink to="/batch" label="Batch" />

            <div className="sidebar-section">Reference</div>
            <SidebarLink to="/variables" label="Variables" />
            <SidebarLink to="/variable-map" label="Variable Map" />
            <SidebarLink to="/audit" label="Audit Log" />
          </>
        )}
      </nav>
      <div className="user-info">
        {user?.display_name}<br />
        <span style={{ textTransform: "capitalize" }}>{user?.role}</span>
      </div>
    </div>
  );
}
