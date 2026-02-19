import "../styles/login.css";

const API_BASE =
  import.meta.env.VITE_AUTH_API_BASE ||
  import.meta.env.VITE_CAMERA_API_BASE ||
  "http://127.0.0.1:9000";

export default function StudentPortal() {
  const start = () => {
    // This should be your FastAPI OIDC login route
    window.location.href = `${API_BASE}/auth/student/login`;
  };

  return (
    <div className="login-page arua-login">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-brand-text">
            <h1 className="login-title">Student Login</h1>
            <p className="login-subtitle">
              You will be redirected to TAMU SSO (OIDC).
            </p>
          </div>
        </div>

        <div className="login-form">
          <button className="login-btn" onClick={start}>
            Continue with TAMU SSO
          </button>

          <div className="login-footnote">
            If nothing opens, your backend may be offline (check /health).
          </div>
        </div>
      </div>
    </div>
  );
}
