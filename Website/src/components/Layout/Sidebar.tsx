import { NavLink } from "react-router-dom";
import { useAuth } from "../../services/authService";
import { useEffect, useState } from "react";
import "../../styles/sidebar.css";

const LS_SIDEBAR_COLLAPSED = "aura-sidebar-collapsed";

export default function Sidebar() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    return localStorage.getItem(LS_SIDEBAR_COLLAPSED) === "1";
  });

  useEffect(() => {
    localStorage.setItem(LS_SIDEBAR_COLLAPSED, collapsed ? "1" : "0");
    document.documentElement.style.setProperty(
      "--sidebar-width",
      collapsed ? "72px" : "240px"
    );
  }, [collapsed]);

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <h1 className="sidebar-title">AURA</h1>
          <p className="sidebar-subtitle">
            {isAdmin ? "Administrator" : "Student Portal"}
          </p>
        </div>

        <button
          type="button"
          className="sidebar-toggle"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section">
          {!collapsed && <span className="sidebar-section-title">Core</span>}

          <NavLink to="/" end className="sidebar-link">
            <span className="sidebar-link-text">Dashboard</span>
          </NavLink>

          <NavLink to="/control" className="sidebar-link">
            <span className="sidebar-link-text">Control</span>
          </NavLink>

          <NavLink to="/camera" className="sidebar-link">
            <span className="sidebar-link-text">Camera</span>
          </NavLink>
        </div>

        <div className="sidebar-section">
          {!collapsed && <span className="sidebar-section-title">AI System</span>}

          <NavLink to="/bot" className="sidebar-link">
            <span className="sidebar-link-text">Simulator</span>
          </NavLink>

          <NavLink to="/files" className="sidebar-link">
            <span className="sidebar-link-text">Files</span>
          </NavLink>
        </div>

        {isAdmin && (
          <div className="sidebar-section">
            {!collapsed && <span className="sidebar-section-title">Admin</span>}

            <NavLink to="/logs" className="sidebar-link admin-link">
              <span className="sidebar-link-text">Chat Logs</span>
            </NavLink>
          </div>
        )}

        <div className="sidebar-bottom">
          <NavLink to="/settings" className="sidebar-link">
            <span className="sidebar-link-text">Settings</span>
          </NavLink>
        </div>
      </nav>
    </aside>
  );
}