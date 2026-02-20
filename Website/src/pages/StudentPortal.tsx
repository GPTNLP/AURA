import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../services/authService";
import "../styles/login.css";
import logo from "../assets/robot.png";

const API_BASE =
  import.meta.env.VITE_AUTH_API_BASE ||
  import.meta.env.VITE_CAMERA_API_BASE ||
  "http://127.0.0.1:9000";

const ALLOWED_DOMAIN = (import.meta.env.VITE_ALLOWED_STUDENT_DOMAIN || "tamu.edu").toLowerCase();

function isValidTamuEmail(email: string) {
  const e = email.trim().toLowerCase();
  return e.endsWith(`@${ALLOWED_DOMAIN}`) && e.includes("@");
}

export default function StudentPortal() {
  const { setSession } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [step, setStep] = useState<"email" | "otp">("email");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [otp, setOtp] = useState("");
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);

  const startStudentLogin = async () => {
    const clean = email.trim().toLowerCase();

    if (!isValidTamuEmail(clean)) {
      throw new Error(`Email must end in @${ALLOWED_DOMAIN}`);
    }

    const res = await fetch(`${API_BASE}/auth/student/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: clean }),
    });

    if (!res.ok) {
      const msg = await res.text();
      throw new Error(msg || "Failed to send code");
    }

    setStep("otp");
  };

  const verifyStudentOtp = async () => {
    setOtpError(null);
    setOtpLoading(true);

    try {
      const res = await fetch(`${API_BASE}/auth/student/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), otp: otp.trim() }),
      });

      if (!res.ok) {
        const msg = await res.text();
        setOtpError(msg || "Invalid code");
        return;
      }

      const data = await res.json();

      // same as admin: update AuthContext (not just localStorage)
      setSession(data.token, data.user);

      // send them to the same dashboard for now (same access as before)
      navigate("/", { replace: true });
    } finally {
      setOtpLoading(false);
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await startStudentLogin();
    } catch (err: any) {
      setError(err?.message || "Could not start student login");
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
            <p className="login-subtitle">TAMU Student Portal</p>
          </div>
        </div>

        {step === "email" && (
          <form onSubmit={handleEmailSubmit} className="login-form">
            <label className="login-label">TAMU Email</label>
            <input
              className="login-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={`netid@${ALLOWED_DOMAIN}`}
              autoComplete="email"
            />

            {error && <div className="login-error">{error}</div>}

            <button className="login-btn" type="submit" disabled={loading}>
              {loading ? "Sending code..." : "Send verification code"}
            </button>

            <button
              type="button"
              className="login-btn login-btn-secondary"
              onClick={() => navigate("/login")}
            >
              ← Back
            </button>

            <div className="login-footnote">
              You’ll receive a 6-digit code at your TAMU email.
            </div>
          </form>
        )}

        {step === "otp" && (
          <div className="login-form">
            <div className="login-footnote" style={{ marginBottom: 8 }}>
              Code sent to <b>{email.trim().toLowerCase()}</b>
            </div>

            <label className="login-label">Verification Code</label>
            <input
              className="login-input"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              placeholder="123456"
              inputMode="numeric"
              maxLength={6}
            />

            {otpError && <div className="login-error">{otpError}</div>}

            <button className="login-btn" onClick={verifyStudentOtp} disabled={otpLoading}>
              {otpLoading ? "Verifying..." : "Verify & Continue"}
            </button>

            <button
              type="button"
              className="login-btn login-btn-secondary"
              onClick={() => {
                setOtp("");
                setOtpError(null);
                setStep("email");
              }}
            >
              ← Use different email
            </button>

            <button
              type="button"
              className="login-btn login-btn-secondary"
              onClick={() => {
                setOtp("");
                setOtpError(null);
                setStep("email");
              }}
            >
              Resend code
            </button>
          </div>
        )}
      </div>
    </div>
  );
}