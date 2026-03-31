import { useEffect, useRef, useState } from "react";
import "../../styles/cameraFeed.css";
import { useAuth } from "../../services/authService";

const API_BASE = import.meta.env.VITE_CAMERA_API_BASE as string | undefined;
const DEVICE_ID = (import.meta.env.VITE_DEVICE_ID as string | undefined) || "jetson-001";

type CameraMode = "raw" | "detection";

export default function CameraFeedSecure() {
  const { token } = useAuth();

  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [src, setSrc] = useState("");
  const [mode, setMode] = useState<CameraMode>("raw");
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState("Idle");

  const mountedRef = useRef(false);
  const refreshTimerRef = useRef<number | null>(null);

  const base = (API_BASE || "").replace(/\/+$/, "");

  const authHeaders = () => ({
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  });

  const buildFrameUrl = () => {
    if (!base) return "";
    return `${base}/camera/latest?device_id=${encodeURIComponent(DEVICE_ID)}&t=${Date.now()}&r=${Math.random()}`;
  };

  const hardClose = () => {
    setSrc("");
    setOk(false);
  };

  const startPolling = () => {
    if (refreshTimerRef.current) {
      window.clearInterval(refreshTimerRef.current);
    }

    refreshTimerRef.current = window.setInterval(() => {
      if (!mountedRef.current) return;
      setSrc(buildFrameUrl());
    }, 350);
  };

  const stopPolling = () => {
    if (refreshTimerRef.current) {
      window.clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  };

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
      setStatusText(newMode === "raw" ? "Raw mode active" : "Detection mode active");

      setSrc(buildFrameUrl());
      startPolling();
    } catch (e: any) {
      setErr(e?.message || "Failed to activate camera");
      setStatusText("Camera start failed");
      hardClose();
    } finally {
      setBusy(false);
    }
  };

  const setCameraMode = async (newMode: CameraMode) => {
    if (!base) return;
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
      // ignore on unmount
    } finally {
      stopPolling();
      setStatusText("Camera off");
      hardClose();
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    activateCamera("raw");

    const onFocus = () => {
      if (!mountedRef.current) return;
      setSrc(buildFrameUrl());
    };

    const onVis = () => {
      if (!mountedRef.current) return;
      if (document.visibilityState === "visible" && src) {
        setSrc(buildFrameUrl());
      }
    };

    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVis);

    return () => {
      mountedRef.current = false;
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVis);
      stopPolling();
      deactivateCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!API_BASE) {
    return (
      <div className="cam-card">
        <div className="cam-card-header">
          <div className="cam-title">Live Camera Feed</div>
          <div className="cam-status bad">● Missing VITE_CAMERA_API_BASE</div>
        </div>
        <div className="cam-help">
          Add <code>VITE_CAMERA_API_BASE</code> and <code>VITE_DEVICE_ID</code> to your frontend env.
        </div>
      </div>
    );
  }

  return (
    <div className="cam-card">
      <div className="cam-card-header" style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ flex: 1 }}>
          <div className="cam-title">Live Camera Feed</div>
          <div className={`cam-status ${ok ? "good" : "bad"}`}>● {ok ? "Connected" : "Disconnected"}</div>
          <div style={{ fontSize: 12, opacity: 0.8, marginTop: 4 }}>{statusText}</div>
        </div>

        <button
          onClick={() => setCameraMode("raw")}
          disabled={busy || mode === "raw"}
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid var(--card-border)",
            background: mode === "raw" ? "var(--accent, #dbeafe)" : "var(--card-bg)",
            fontWeight: 900,
            cursor: busy || mode === "raw" ? "not-allowed" : "pointer",
            opacity: busy || mode === "raw" ? 0.7 : 1,
          }}
        >
          Raw
        </button>

        <button
          onClick={() => setCameraMode("detection")}
          disabled={busy || mode === "detection"}
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid var(--card-border)",
            background: mode === "detection" ? "var(--accent, #dbeafe)" : "var(--card-bg)",
            fontWeight: 900,
            cursor: busy || mode === "detection" ? "not-allowed" : "pointer",
            opacity: busy || mode === "detection" ? 0.7 : 1,
          }}
        >
          Detection
        </button>

        <button
          onClick={() => activateCamera(mode)}
          disabled={busy}
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid var(--card-border)",
            background: "var(--card-bg)",
            fontWeight: 900,
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.7 : 1,
          }}
        >
          Refresh
        </button>
      </div>

      <div className="cam-frame" style={{ position: "relative" }}>
        {src ? (
          <img
            className="cam-img"
            src={src}
            alt="Camera stream"
            onLoad={() => {
              setOk(true);
              setErr(null);
            }}
            onError={() => {
              setOk(false);
              setErr("Frame unavailable yet");
            }}
          />
        ) : (
          <div className="cam-help">Connecting...</div>
        )}
      </div>

      {err && <div className="cam-error">{err}</div>}
    </div>
  );
}