import { useAuth } from "../../services/authService";
import "../../styles/navbar.css";

export default function Navbar() {
    const { user, logout } = useAuth();

    return (
        <header className="navbar">
            <span className="navbar-title">ARUA Control Panel</span>

            <div className="navbar-right">
                <span className="navbar-user">{user?.email}</span>
                <button className="navbar-logout" onClick={logout}>
                    Logout
                </button>
            </div>
        </header>
    );
}
