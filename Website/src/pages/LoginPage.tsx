import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";
import AdminOtpModal from "../components/AdminOtpModal";

export default function LoginPage() {
  const { adminStartLogin, adminVerifyOtp } = useAuth();
  const navigate = useNavigate();

  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // OTP modal state
  const [showOtp, setShowOtp] = useState(false);
  const [otpEmail, setOtpEmail] = useState("");
  const [otpError, setOtpError] = useState<string | null>(null);

  // =========================
  // Admin OTP Start
  // =========================
  const startAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const email = adminEmail.trim().toLowerCase();
      await adminStartLogin(email, adminPassword);

      setOtpEmail(email);
      setOtpError(null);
      setShowOtp(true);
    } catch (err: any) {
      setError(err?.message || "Invalid admin credentials.");
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // OTP Verify (Admin)
  // =========================
  const verifyOtp = async (otp: string) => {
    setOtpError(null);

    try {
      await adminVerifyOtp(otpEmail, otp);
      setShowOtp(false);
      navigate("/", { replace: true });
    } catch (err: any) {
      setOtpError(err?.message || "Invalid OTP");
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

        <form onSubmit={startAdmin} className="login-form">
          <label className="login-label">Admin Email</label>
          <input
            className="login-input"
            value={adminEmail}
            onChange={(e) => setAdminEmail(e.target.value)}
            placeholder="admin@email.com"
            autoComplete="email"
          />

          <label className="login-label">Password</label>
          <input
            className="login-input"
            type="password"
            value={adminPassword}
            onChange={(e) => setAdminPassword(e.target.value)}
            placeholder="Enter admin password"
            autoComplete="current-password"
          />

          {error && <div className="login-error">{error}</div>}

          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? "Sending code..." : "Send Code"}
          </button>

          <div className="login-footnote">Admin access only</div>
        </form>
      </div>

      {showOtp && (
        <AdminOtpModal
          email={otpEmail}
          error={otpError}
          onCancel={() => setShowOtp(false)}
          onVerify={verifyOtp}
        />
      )}
    </div>
  );
}