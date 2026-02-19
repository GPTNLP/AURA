import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";
import AdminOtpModal from "../components/AdminOtpModal";

import { useMsal } from "@azure/msal-react";

const API_BASE =
  import.meta.env.VITE_AUTH_API_BASE ||
  import.meta.env.VITE_CAMERA_API_BASE ||
  "http://127.0.0.1:9000";

const AZURE_SCOPES = String(import.meta.env.VITE_AZURE_SCOPES || "openid,profile,email")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

export default function LoginPage() {
  const { setSession } = useAuth();
  const navigate = useNavigate();
  const { instance } = useMsal();

  const [mode, setMode] = useState<"select" | "admin">("select");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [showOtp, setShowOtp] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);

  // =========================
  // Student (MSAL) Login
  // =========================
  const handleStudentLogin = async () => {
    setError(null);
    setLoading(true);

    try {
      const result = await instance.loginPopup({
        scopes: AZURE_SCOPES,
        prompt: "select_account",
      });

      const claims: any = result?.account?.idTokenClaims || {};
      const userEmail: string =
        claims?.email ||
        claims?.preferred_username ||
        result?.account?.username ||
        "";

      if (!userEmail) throw new Error("Microsoft login succeeded but no email was returned.");
      if (!userEmail.toLowerCase().endsWith("@tamu.edu")) {
        throw new Error("Only TAMU accounts are allowed.");
      }

      const idToken = (result as any)?.idToken || "msal-session";

      // Create a frontend session for your existing ProtectedRoute flow
      setSession(idToken, { email: userEmail, role: "student" });

      // Your dashboard is "/", not "/dashboard"
      navigate("/", { replace: true });
    } catch (e: any) {
      setError(e?.message || "Student login failed.");
    } finally {
      setLoading(false);
    }
  };

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
    setSession(data.token, data.user);

    setShowOtp(false);
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
    <div className="aura-login login-page">
      <div className="login-card">
        <div className="login-brand">
          <img src={logo} alt="AURA" className="login-logo" />
          <div className="login-brand-text">
            <h1 className="login-title">AURA</h1>
            <p className="login-subtitle">Control Panel Access</p>
          </div>
        </div>

        {mode === "select" && (
          <div className="login-form">
            {error && <div className="login-error">{error}</div>}

            <button
              className="login-btn"
              onClick={() => setMode("admin")}
              disabled={loading}
            >
              Admin Login
            </button>

            <button
              className="login-btn login-btn-secondary"
              onClick={handleStudentLogin}
              disabled={loading}
              title="Sign in with Microsoft (TAMU)"
            >
              {loading ? "Signing in..." : "TAMU Student Login"}
            </button>

            <div className="login-footnote">Choose your access portal</div>
          </div>
        )}

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
              disabled={loading}
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