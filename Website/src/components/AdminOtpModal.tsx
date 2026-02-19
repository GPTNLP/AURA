import { useEffect, useRef, useState } from "react";
import "../styles/login.css";

type Props = {
  email: string;
  onVerify: (otp: string) => Promise<void>;
  onCancel: () => void;
  error?: string | null;
};

export default function AdminOtpModal({ email, onVerify, onCancel, error }: Props) {
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const submit = async () => {
    if (!otp.trim()) return;
    setLoading(true);
    try {
      await onVerify(otp.trim());
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="otp-overlay">
      <div className="otp-card" onClick={(e) => e.stopPropagation()}>
        <div className="otp-header">
          <div className="otp-title">Admin verification</div>
          <div className="otp-subtitle">
            Code sent to <b>{email}</b>
          </div>
        </div>

        <input
          ref={inputRef}
          className="otp-input"
          value={otp}
          onChange={(e) => setOtp(e.target.value)}
          placeholder="Enter 6-digit code"
          inputMode="numeric"
          autoComplete="one-time-code"
        />

        {error && <div className="login-error" style={{ marginTop: 10 }}>{error}</div>}

        <div className="otp-actions">
          <button type="button" className="otp-btn otp-cancel" onClick={onCancel} disabled={loading}>
            Cancel
          </button>
          <button type="button" className="otp-btn otp-verify" onClick={submit} disabled={loading}>
            {loading ? "Verifying..." : "Verify"}
          </button>
        </div>

        <div className="otp-footnote">Tip: copy/paste works</div>
      </div>
    </div>
  );
}
