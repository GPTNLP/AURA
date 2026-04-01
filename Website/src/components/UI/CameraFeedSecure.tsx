import { useEffect, useMemo, useState } from "react";
import "../../styles/cameraFeed.css";
import { useAuth } from "../../services/authService";

const API_BASE = import.meta.env.VITE_CAMERA_API_BASE as string | undefined;
const DEVICE_ID = (import.meta.env.VITE_DEVICE_ID as string | undefined) || "jetson-001";

type CameraMode = "raw" | "detection";

export default function CameraFeedSecure() {
  const { token } = useAuth();

  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<CameraMode>("raw");
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState("Idle");
  const [streamNonce, setStreamNonce] = useState(0);

  const base = (API_BASE || "").replace(/\/+$/, "");

  const authHeaders = () => ({
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  });

  const streamSrc = useMemo(() => {
    if (!base) return "";
    return `${base}/camera/stream?device_id=${encodeURIComponent(DEVICE_ID)}&mode=${encodeURIComponent(mode)}&n=${streamNonce}`;
  }, [base, mode, streamNonce]);

  const activateCamera = async (newMode: CameraMode) => {
    if (!base) return;

    setBusy(true);
    setErr(null);
    setStatusText(`Starting ${newMode}...`);

    try {
      const res = await fetch(
        `${base}/camera/control/activate?device_id=${encodeURIComponent(DEVICE_ID)}&mode=${encodeURIComponent(newMode)}`,
        {
          method: "POST",
          credentials: "include",
          headers: authHeaders(),
        }
      );

      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.detail || `Activate failed (${res.status})`);
      }

      setMode(newMode);
      setOk(false);
      setErr(null);
      setStatusText(newMode === "raw" ? "Raw mode active" : "Detection mode active");
      setStreamNonce((n) => n + 1);
    } catch (e: any) {
      setErr(e?.message || "Failed to activate camera");
      setStatusText("Camera start failed");
      setOk(false);
    } finally {
      setBusy(false);
    }
  };

  const setCameraMode = async (newMode: CameraMode) => {
    if (busy) return;
    if (mode === newMode) return;
    await activateCamera(newMode);
  };

  const deactivateCamera = async () => {
    if (!base) return;

    try {
      await fetch(
        `${base}/camera/control/deactivate?device_id=${encodeURIComponent(DEVICE_ID)}`,
        {
          method: "POST",
          credentials: "include",
          headers: authHeaders(),
        }
      );
    } catch {
      // ignore
    } finally {
      setStatusText("Camera off");
      setOk(false);
      setStreamNonce((n) => n + 1);
    }
  };

  useEffect(() => {
    activateCamera("raw");

    return () => {
      deactivateCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!API_BASE) {
    return (
      <div className="cam-card">
        <div className="cam-title">Missing API base</div>
      </div>
    );
  }

  const buttonBaseStyle: React.CSSProperties = {
    padding: "10px 16px",
    borderRadius: "12px",
    border: "1px solid rgba(255,255,255,0.12)",
    background: "rgba(255,255,255,0.04)",
    color: "var(--text-primary, #fff)",
    fontWeight: 700,
    fontSize: "0.95rem",
    cursor: busy ? "not-allowed" : "pointer",
    transition: "all 0.18s ease",
    minWidth: "96px",
    backdropFilter: "blur(6px)",
  };

  const activeButtonStyle: React.CSSProperties = {
    background: "linear-gradient(135deg, rgba(99,102,241,0.95), rgba(139,92,246,0.95))",
    border: "1px solid rgba(139,92,246,0.95)",
    color: "#fff",
    boxShadow: "0 0 0 1px rgba(139,92,246,0.15), 0 8px 24px rgba(99,102,241,0.28)",
  };

  const inactiveButtonStyle: React.CSSProperties = {
    opacity: busy ? 0.6 : 0.92,
  };

  return (
    <div className="cam-card">
      <div
        className="cam-card-header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 18,
          flexWrap: "wrap",
          paddingBottom: 12,
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          marginBottom: 14,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div className="cam-title">Live Camera Feed</div>
          <div
            className={`cam-status ${ok ? "good" : "bad"}`}
            style={{
              fontWeight: 700,
              fontSize: "0.95rem",
            }}
          >
            {ok ? "● Live" : "● Waiting"}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "center",
            justifyContent: "flex-end",
            flexWrap: "wrap",
          }}
        >
          <button
            onClick={() => setCameraMode("raw")}
            disabled={busy}
            style={{
              ...buttonBaseStyle,
              ...(mode === "raw" ? activeButtonStyle : inactiveButtonStyle),
            }}
          >
            Raw
          </button>

          <button
            onClick={() => setCameraMode("detection")}
            disabled={busy}
            style={{
              ...buttonBaseStyle,
              ...(mode === "detection" ? activeButtonStyle : inactiveButtonStyle),
            }}
          >
            Detection
          </button>

          <button
            onClick={() => setStreamNonce((n) => n + 1)}
            disabled={busy}
            style={{
              ...buttonBaseStyle,
              ...inactiveButtonStyle,
            }}
          >
            Refresh
          </button>
        </div>
      </div>

      <div
        className="cam-substatus"
        style={{
          marginBottom: 12,
          fontSize: "1rem",
          fontWeight: 500,
          opacity: 0.92,
        }}
      >
        {statusText}
      </div>

      <div
        className="cam-frame"
        style={{
          position: "relative",
          overflow: "hidden",
          borderRadius: 22,
        }}
      >
        <img
          key={streamSrc}
          className="cam-img"
          src={streamSrc}
          alt="Camera stream"
          onLoad={() => {
            setOk(true);
            setErr(null);
          }}
          onError={() => {
            setOk(false);
            setErr("Stream unavailable");
          }}
        />
      </div>

      {err && <div className="cam-error">{err}</div>}
    </div>
  );
}