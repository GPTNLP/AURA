import "../styles/login.css";
import logo from "../assets/robot.png";

export default function StudentPortal() {
  return (
    <div className="aura-login login-page">
      <div className="login-card">
        <div className="login-brand">
          <img src={logo} alt="AURA" className="login-logo" />
          <div className="login-brand-text">
            <h1 className="login-title">TAMU Student Login</h1>
            <p className="login-subtitle">
              Student login is handled on the main login screen.
            </p>
          </div>
        </div>

        <div className="login-form">
          <button
            className="login-btn login-btn-secondary"
            onClick={() => window.history.back()}
          >
            ← Back to Login
          </button>

          <div className="login-footnote">
            If you want backend OIDC later, we’ll wire it here.
          </div>
        </div>
      </div>
    </div>
  );
}