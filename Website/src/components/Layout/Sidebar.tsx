import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../services/authService";
import { useEffect, useState } from "react";
import "../../styles/sidebar.css";

const LS_SIDEBAR_COLLAPSED = "aura-sidebar-collapsed";

export default function Sidebar() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const role = user?.role;
  const isAdmin = role === "admin";
  const isTA = role === "ta";

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    return localStorage.getItem(LS_SIDEBAR_COLLAPSED) === "1";
  });

  useEffect(() => {
    localStorage.setItem(LS_SIDEBAR_COLLAPSED, collapsed ? "1" : "0");
    document.documentElement.style.setProperty("--sidebar-width", collapsed ? "72px" : "240px");
  }, [collapsed]);

  useEffect(() => {
    const path = location.pathname;

    const adminOnly =
      path === "/control" ||
      path === "/logs" ||
      path.startsWith("/admin/");

    const taOrAdminOnly =
      path === "/database" || path === "/files";

    if (adminOnly && !isAdmin) {
      navigate("/dashboard", { replace: true });
      return;
    }

    if (taOrAdminOnly && !(isAdmin || isTA)) {
      navigate("/dashboard", { replace: true });
    }
  }, [location.pathname, isAdmin, isTA, navigate]);

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `sidebar-link ${isActive ? "active" : ""}`;

  const adminLinkClass = ({ isActive }: { isActive: boolean }) =>
    `sidebar-link admin-link ${isActive ? "active" : ""}`;

  const portalLabel = isAdmin ? "Administrator" : isTA ? "TA Portal" : "Student Portal";

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-top">
        <div className="sidebar-brand">
          <h1 className="sidebar-title">AURA</h1>
          <p className="sidebar-subtitle">{portalLabel}</p>
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

          <NavLink to="/" end className={linkClass}>
            <span className="sidebar-link-text">Dashboard</span>
          </NavLink>

          {isAdmin && (
            <NavLink to="/control" className={linkClass}>
              <span className="sidebar-link-text">Control</span>
            </NavLink>
          )}

          <NavLink to="/camera" className={linkClass}>
            <span className="sidebar-link-text">Camera</span>
          </NavLink>
        </div>

        <div className="sidebar-section">
          {!collapsed && <span className="sidebar-section-title">AI System</span>}

          <NavLink to="/simulator" className={linkClass}>
            <span className="sidebar-link-text">Simulator</span>
          </NavLink>

          {(isAdmin || isTA) && (
            <NavLink to="/database" className={linkClass}>
              <span className="sidebar-link-text">Database</span>
            </NavLink>
          )}
        </div>

        {isAdmin && (
          <div className="sidebar-section">
            {!collapsed && <span className="sidebar-section-title">Admin</span>}

            <NavLink to="/logs" className={adminLinkClass}>
              <span className="sidebar-link-text">Chat Logs</span>
            </NavLink>

            <NavLink to="/admin/ta" className={adminLinkClass}>
              <span className="sidebar-link-text">TA Manager</span>
            </NavLink>

            <NavLink to="/admin/admins" className={adminLinkClass}>
              <span className="sidebar-link-text">Admins</span>
            </NavLink>
          </div>
        )}

        <div className="sidebar-bottom">
          <NavLink to="/settings" className={linkClass}>
            <span className="sidebar-link-text">Settings</span>
          </NavLink>
        </div>
      </nav>
    </aside>
  );
}