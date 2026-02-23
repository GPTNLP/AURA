import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";
import AdminOtpModal from "../components/AdminOtpModal";

function isTamuEmail(email: string) {
  return email.trim().toLowerCase().endsWith("@tamu.edu");
}

export default function LoginTAPage() {
  const { taStartLogin, taVerifyOtp, refreshMe, user, logout } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
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
      if (!isTamuEmail(em)) throw new Error("Please use your @tamu.edu email.");

      await taStartLogin(em);

      setOtpEmail(em);
      setOtpError(null);
      setShowOtp(true);
    } catch (err: any) {
      setError(err?.message || "TA login failed.");
    } finally {
      setLoading(false);
    }
  };

  const verify = async (otp: string) => {
    setOtpError(null);
    try {
      await taVerifyOtp(otpEmail, otp);

      // Pull the current user/role from backend
      await refreshMe();

      // Extra safety: if somehow not TA, force logout
      if (user?.role && user.role !== "ta") {
        logout();
        throw new Error("This account is not authorized as a TA.");
      }

      setShowOtp(false);

      // TA should land somewhere they can access
      navigate("/database", { replace: true });
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
            <p className="login-subtitle">TA Login</p>
          </div>
        </div>

        <form onSubmit={start} className="login-form">
          <label className="login-label">TAMU Email</label>
          <input
            className="login-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="netid@tamu.edu"
            autoComplete="email"
          />

          {error && <div className="login-error">{error}</div>}

          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? "Sending code..." : "Send Code"}
          </button>

          <div className="login-footnote">TAs: admin approval + email + 2FA</div>
        </form>
      </div>

      {showOtp && (
        <AdminOtpModal
          title="TA verification"
          email={otpEmail}
          error={otpError}
          onCancel={() => setShowOtp(false)}
          onVerify={verify}
        />
      )}
    </div>
  );
}