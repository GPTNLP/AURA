import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";
import AdminOtpModal from "../components/AdminOtpModal";

const API_BASE =
  import.meta.env.VITE_AUTH_API_BASE ||
  import.meta.env.VITE_CAMERA_API_BASE ||
  "http://127.0.0.1:9000";

export default function LoginPage() {
  const { login, setSession } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<"select" | "admin">("select");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [showOtp, setShowOtp] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);

  // =========================
  // Admin login (Step 1)
  // =========================
  const startAdminLogin = async () => {
    const res = await fetch(`${API_BASE}/auth/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), password }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Admin login failed");
    }

    setShowOtp(true);
  };

  // =========================
  // Admin OTP verify (Step 2)
  // =========================
  const verifyAdminOtp = async (otp: string) => {
    setOtpError(null);

    const res = await fetch(`${API_BASE}/auth/admin/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim(), otp }),
    });

    if (!res.ok) {
      const msg = await res.text();
      setOtpError(msg || "Invalid OTP");
      return;
    }

    const data = await res.json();

    // ✅ IMPORTANT: update AuthContext state (not just localStorage)
    setSession(data.token, data.user);

    setShowOtp(false);

    // Go to your ML admin page route (matches your router)
    navigate("/ml-admin", { replace: true });
  };

  const handleAdminSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await startAdminLogin();
    } catch {
      setError("Invalid admin credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="arua-login login-page">
      <div className="login-card">
        <div className="login-brand">
          <img src={logo} alt="ARUA" className="login-logo" />
          <div className="login-brand-text">
            <h1 className="login-title">ARUA</h1>
            <p className="login-subtitle">Control Panel Access</p>
          </div>
        </div>

        {/* SELECT */}
        {mode === "select" && (
          <div className="login-form">
            <button className="login-btn" onClick={() => setMode("admin")}>
              Admin Login
            </button>

            <button
              className="login-btn login-btn-secondary"
              onClick={() => navigate("/student-portal")}
            >
              TAMU Student Login
            </button>

            <div className="login-footnote">Choose your access portal</div>
          </div>
        )}

        {/* ADMIN */}
        {mode === "admin" && (
          <form onSubmit={handleAdminSubmit} className="login-form">
            <label className="login-label">Admin Email</label>
            <input
              className="login-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@email.com"
              autoComplete="email"
            />

            <label className="login-label">Password</label>
            <input
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter admin password"
              autoComplete="current-password"
            />

            {error && <div className="login-error">{error}</div>}

            <button className="login-btn" type="submit" disabled={loading}>
              {loading ? "Verifying..." : "Login"}
            </button>

            <button
              type="button"
              className="login-btn login-btn-secondary"
              onClick={() => setMode("select")}
            >
              ← Back
            </button>
          </form>
        )}
      </div>

      {showOtp && (
        <AdminOtpModal
          email={email.trim()}
          error={otpError}
          onCancel={() => setShowOtp(false)}
          onVerify={verifyAdminOtp}
        />
      )}
    </div>
  );
}
