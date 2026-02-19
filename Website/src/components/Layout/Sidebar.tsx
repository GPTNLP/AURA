import { NavLink } from "react-router-dom";
import "../../styles/sidebar.css";

export default function Sidebar() {
    return (
        <aside className="sidebar">
            <h1 className="sidebar-title">AURA</h1>

            <nav className="sidebar-nav">
                <NavLink to="/" end className="sidebar-link">
                    Dashboard
                </NavLink>

                <NavLink to="/control" className="sidebar-link">
                    Control
                </NavLink>

                <NavLink to="/camera" className="sidebar-link">
                    Camera
                </NavLink>

                <NavLink to="/settings" className="sidebar-link">
                    Settings
                </NavLink>
            </nav>
        </aside>
    );
}
