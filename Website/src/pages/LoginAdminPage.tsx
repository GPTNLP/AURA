import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";
import AdminOtpModal from "../components/AdminOtpModal";

export default function LoginAdminPage() {
  const { adminStartLogin, adminVerifyOtp } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [showOtp, setShowOtp] = useState(false);
  const [otpEmail, setOtpEmail] = useState("");
  const [otpError, setOtpError] = useState<string | null>(null);

  const start = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const em = email.trim().toLowerCase();
      if (!em) throw new Error("Enter your admin email.");
      if (!password.trim()) throw new Error("Enter your admin password.");

      await adminStartLogin(em, password);

      setOtpEmail(em);
      setOtpError(null);
      setShowOtp(true);
    } catch (err: any) {
      setError(err?.message || "Admin login failed.");
    } finally {
      setLoading(false);
    }
  };

  const verify = async (otp: string) => {
    setOtpError(null);
    try {
      await adminVerifyOtp(otpEmail, otp);
      setShowOtp(false);
      navigate("/dashboard", { replace: true });
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
            <p className="login-subtitle">Admin Portal</p>
          </div>
        </div>

        <form onSubmit={start} className="login-form">
          <label className="login-label">Admin Email</label>
          <input
            className="login-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="admin@tamu.edu"
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
            {loading ? "Sending code..." : "Send Code"}
          </button>

          <div className="login-footnote">Admin: email + password + 2FA</div>
        </form>
      </div>

      {showOtp && (
        <AdminOtpModal
          title="Admin verification"
          email={otpEmail}
          error={otpError}
          onCancel={() => setShowOtp(false)}
          onVerify={verify}
        />
      )}
    </div>
  );
}