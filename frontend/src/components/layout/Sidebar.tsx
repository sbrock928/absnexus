import { NavLink } from "react-router-dom";
import { useAuth } from "../../auth";

export function Sidebar() {
  const { user, isAdmin } = useAuth();

  return (
    <div className="sidebar">
      <div className="sidebar-brand">ABSNexus</div>
      <nav>
        <NavLink to="/deals" className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
          Deals
        </NavLink>
        <NavLink to="/variables" className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
          Variables
        </NavLink>
        <NavLink to="/variable-map" className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
          Variable Map
        </NavLink>
        <NavLink to="/processing" className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
          Processing
        </NavLink>
        <NavLink to="/batch" className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
          Batch
        </NavLink>
        <NavLink to="/audit" className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
          Audit Log
        </NavLink>
        {isAdmin && (
          <NavLink to="/users" className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
            Users
          </NavLink>
        )}
      </nav>
      <div className="user-info">
        {user?.display_name}<br />
        <span style={{ textTransform: "capitalize" }}>{user?.role}</span>
      </div>
    </div>
  );
}
