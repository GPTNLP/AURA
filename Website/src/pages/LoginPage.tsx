import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";
import AdminOtpModal from "../components/AdminOtpModal";

export default function LoginPage() {
  const { adminStartLogin, adminVerifyOtp, studentStart, studentVerify } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<"select" | "admin" | "student">("select");

  // admin fields
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");

  // student field
  const [studentEmail, setStudentEmail] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // OTP modal state
  const [showOtp, setShowOtp] = useState(false);
  const [otpMode, setOtpMode] = useState<"admin" | "student">("admin");
  const [otpEmail, setOtpEmail] = useState("");
  const [otpError, setOtpError] = useState<string | null>(null);

  // =========================
  // Student OTP Start
  // =========================
  const startStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const email = studentEmail.trim().toLowerCase();
      if (!email.endsWith("@tamu.edu")) throw new Error("Only TAMU emails are allowed.");

      await studentStart(email);

      setOtpMode("student");
      setOtpEmail(email);
      setOtpError(null);
      setShowOtp(true);
    } catch (err: any) {
      setError(err?.message || "Student login failed.");
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // Admin OTP Start
  // =========================
  const startAdmin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await adminStartLogin(adminEmail.trim(), adminPassword);
      setOtpMode("admin");
      setOtpEmail(adminEmail.trim().toLowerCase());
      setOtpError(null);
      setShowOtp(true);
    } catch {
      setError("Invalid admin credentials.");
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // OTP Verify (Admin or Student)
  // =========================
  const verifyOtp = async (otp: string) => {
    setOtpError(null);
    try {
      if (otpMode === "admin") {
        await adminVerifyOtp(otpEmail, otp);
      } else {
        await studentVerify(otpEmail, otp);
      }

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

        {mode === "select" && (
          <div className="login-form">
            {error && <div className="login-error">{error}</div>}

            <button className="login-btn" onClick={() => setMode("admin")} disabled={loading}>
              Admin Login
            </button>

            <button
              className="login-btn login-btn-secondary"
              onClick={() => setMode("student")}
              disabled={loading}
            >
              Student Login (TAMU Email OTP)
            </button>

            <div className="login-footnote">Choose your access portal</div>
          </div>
        )}

        {mode === "admin" && (
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

        {mode === "student" && (
          <form onSubmit={startStudent} className="login-form">
            <label className="login-label">TAMU Email</label>
            <input
              className="login-input"
              value={studentEmail}
              onChange={(e) => setStudentEmail(e.target.value)}
              placeholder="netid@tamu.edu"
              autoComplete="email"
            />

            {error && <div className="login-error">{error}</div>}

            <button className="login-btn" type="submit" disabled={loading}>
              {loading ? "Sending code..." : "Send Code"}
            </button>

            <button
              type="button"
              className="login-btn login-btn-secondary"
              onClick={() => setMode("select")}
              disabled={loading}
            >
              ← Back
            </button>

            <div className="login-footnote">
              We’ll email a 6-digit code. No password is stored.
            </div>
          </form>
        )}
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