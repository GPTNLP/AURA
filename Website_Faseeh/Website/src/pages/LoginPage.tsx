import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("student@tamu.edu");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err: any) {
      setError("Login failed. Check email + password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <img src={logo} alt="ARUA" className="login-logo" />
          <div className="login-brand-text">
            <h1 className="login-title">ARUA</h1>
            <p className="login-subtitle">Control Panel Access</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <label className="login-label" htmlFor="email">Email</label>
          <input
            id="email"
            className="login-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="student@tamu.edu"
            autoComplete="email"
          />

          <label className="login-label" htmlFor="password">Password</label>
          <input
            id="password"
            className="login-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter access password"
            type="password"
            autoComplete="current-password"
          />

          {error && <div className="login-error">{error}</div>}

          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? "Logging in..." : "Login"}
          </button>

          <div className="login-footnote">Backend auth (temporary)</div>
        </form>
      </div>
    </div>
  );
}
