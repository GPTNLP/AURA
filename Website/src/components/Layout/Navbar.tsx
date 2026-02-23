import { useAuth } from "../../services/authService";
import "../../styles/navbar.css";

export default function Navbar() {
  const { user, logout } = useAuth();

  const roleLabel =
    user?.role === "admin" ? "Admin" : user?.role === "ta" ? "TA" : "Student";

  return (
    <header className="navbar">
      <span className="navbar-title">AURA Control Panel</span>

      <div className="navbar-right">
        <span className="navbar-user">
          {user?.email} {user?.email ? `(${roleLabel})` : ""}
        </span>
        <button className="navbar-logout" onClick={logout}>
          Logout
        </button>
      </div>
    </header>
  );
}