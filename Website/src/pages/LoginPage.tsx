import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";
import AdminOtpModal from "../components/AdminOtpModal";

export default function LoginPage() {
  const { adminStartLogin, adminVerifyOtp, studentStartLogin, studentVerifyOtp } = useAuth();
  const navigate = useNavigate();

  // UI mode
  const [mode, setMode] = useState<"student" | "admin">("student");

  // Student fields
  const [studentEmail, setStudentEmail] = useState("");

  // Admin fields
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // OTP modal state
  const [showOtp, setShowOtp] = useState(false);
  const [otpEmail, setOtpEmail] = useState("");
  const [otpError, setOtpError] = useState<string | null>(null);
  const [otpTitle, setOtpTitle] = useState("Verification");

  const isTamuEmail = (email: string) => email.trim().toLowerCase().endsWith("@tamu.edu");

  // =========================
  // Start Login
  // =========================
  const start = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "student") {
        const email = studentEmail.trim().toLowerCase();
        if (!isTamuEmail(email)) throw new Error("Student email must end with @tamu.edu");

        await studentStartLogin(email);

        setOtpEmail(email);
        setOtpTitle("Student verification");
        setOtpError(null);
        setShowOtp(true);
        return;
      }

      // admin
      const email = adminEmail.trim().toLowerCase();
      await adminStartLogin(email, adminPassword);

      setOtpEmail(email);
      setOtpTitle("Admin verification");
      setOtpError(null);
      setShowOtp(true);
    } catch (err: any) {
      setError(err?.message || "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // Verify OTP
  // =========================
  const verifyOtp = async (otp: string) => {
    setOtpError(null);

    try {
      if (mode === "student") {
        await studentVerifyOtp(otpEmail, otp);
      } else {
        await adminVerifyOtp(otpEmail, otp);
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

        {/* Mode toggle */}
        <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
          <button
            type="button"
            className="login-btn"
            style={{ flex: 1, opacity: mode === "student" ? 1 : 0.6 }}
            onClick={() => {
              setMode("student");
              setError(null);
            }}
          >
            Student
          </button>
          <button
            type="button"
            className="login-btn"
            style={{ flex: 1, opacity: mode === "admin" ? 1 : 0.6 }}
            onClick={() => {
              setMode("admin");
              setError(null);
            }}
          >
            Admin
          </button>
        </div>

        <form onSubmit={start} className="login-form">
          {mode === "student" ? (
            <>
              <label className="login-label">Student Email</label>
              <input
                className="login-input"
                value={studentEmail}
                onChange={(e) => setStudentEmail(e.target.value)}
                placeholder="netid@tamu.edu"
                autoComplete="email"
              />
              <div className="login-footnote">Student access requires @tamu.edu</div>
            </>
          ) : (
            <>
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

              <div className="login-footnote">Admin access only</div>
            </>
          )}

          {error && <div className="login-error">{error}</div>}

          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? "Sending code..." : "Send Code"}
          </button>
        </form>
      </div>

      {showOtp && (
        <AdminOtpModal
          title={otpTitle}
          email={otpEmail}
          error={otpError}
          onCancel={() => setShowOtp(false)}
          onVerify={verifyOtp}
        />
      )}
    </div>
  );
}