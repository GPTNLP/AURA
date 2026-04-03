import { useEffect, useMemo, useRef, useState } from "react";
import "../../styles/cameraFeed.css";
import { useAuth } from "../../services/authService";

const API_BASE = import.meta.env.VITE_CAMERA_API_BASE as string | undefined;
const DEVICE_ID =
  (import.meta.env.VITE_DEVICE_ID as string | undefined) || "jetson-001";

type CameraMode = "raw" | "detection";

type CameraMeta = {
  ok?: boolean;
  device_id?: string;
  available?: boolean;
  mode?: CameraMode;
  updated_at?: number;
  bytes?: number;
};

export default function CameraFeedSecure() {
  const { token } = useAuth();

  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<CameraMode>("raw");
  const [busy, setBusy] = useState(false);
  const [displaySrc, setDisplaySrc] = useState("");
  const [statusText, setStatusText] = useState("Starting camera...");
  const [metaTick, setMetaTick] = useState(0);

  const mountedRef = useRef(true);
  const preloadRef = useRef<HTMLImageElement | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const metaTimerRef = useRef<number | null>(null);

  const base = (API_BASE || "").replace(/\/+$/, "");

  const authHeaders = () => ({
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  });

  const frameSrc = useMemo(() => {
    if (!base) return "";
    return `${base}/camera/latest?device_id=${encodeURIComponent(
      DEVICE_ID
    )}&mode=${encodeURIComponent(mode)}&t=${Date.now()}`;
  }, [base, mode, metaTick]);

  const metaUrl = useMemo(() => {
    if (!base) return "";
    return `${base}/camera/latest/meta?device_id=${encodeURIComponent(DEVICE_ID)}`;
  }, [base]);

  const activateCamera = async (newMode: CameraMode) => {
    if (!base) return;

    setBusy(true);
    setErr(null);
    setStatusText(newMode === "raw" ? "Starting raw mode..." : "Starting detection...");

    try {
      const res = await fetch(
        `${base}/camera/control/activate?device_id=${encodeURIComponent(
          DEVICE_ID
        )}&mode=${encodeURIComponent(newMode)}`,
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
      setDisplaySrc("");
      setStatusText(newMode === "raw" ? "Raw mode active" : "Detection mode active");
      setMetaTick((n) => n + 1);
    } catch (e: any) {
      setErr(e?.message || "Failed to activate camera");
      setStatusText("Camera start failed");
      setOk(false);
    } finally {
      setBusy(false);
    }
  };

  const deactivateCamera = async () => {
    if (!base) return;

    try {
      await fetch(
        `${base}/camera/control/deactivate?device_id=${encodeURIComponent(
          DEVICE_ID
        )}`,
        {
          method: "POST",
          credentials: "include",
          headers: authHeaders(),
          keepalive: true,
        }
      );
    } catch {
      // ignore
    } finally {
      if (!mountedRef.current) return;
      setOk(false);
      setStatusText("Camera off");
    }
  };

  const setCameraMode = async (newMode: CameraMode) => {
    if (busy) return;
    if (mode === newMode) return;
    await activateCamera(newMode);
  };

  const loadNextFrame = (src: string) => {
    if (!src) return;

    const img = new Image();
    preloadRef.current = img;

    img.onload = () => {
      if (!mountedRef.current) return;
      if (preloadRef.current !== img) return;
      setDisplaySrc(src);
      setOk(true);
      setErr(null);
    };

    img.onerror = () => {
      if (!mountedRef.current) return;
      if (preloadRef.current !== img) return;
      setOk(false);
      setErr("Stream unavailable");
    };

    img.src = src;
  };

  useEffect(() => {
    mountedRef.current = true;

    const start = async () => {
      await activateCamera("raw");
    };

    start();

    const onPageHide = () => {
      fetch(
        `${base}/camera/control/deactivate?device_id=${encodeURIComponent(DEVICE_ID)}`,
        {
          method: "POST",
          credentials: "include",
          headers: authHeaders(),
          keepalive: true,
        }
      ).catch(() => {});
    };

    window.addEventListener("pagehide", onPageHide);

    return () => {
      mountedRef.current = false;

      if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);
      if (metaTimerRef.current) window.clearInterval(metaTimerRef.current);

      window.removeEventListener("pagehide", onPageHide);
      deactivateCamera();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!base) return;

    if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);

    pollTimerRef.current = window.setInterval(() => {
      loadNextFrame(
        `${base}/camera/latest?device_id=${encodeURIComponent(
          DEVICE_ID
        )}&mode=${encodeURIComponent(mode)}&t=${Date.now()}`
      );
    }, 120);

    return () => {
      if (pollTimerRef.current) window.clearInterval(pollTimerRef.current);
    };
  }, [base, mode]);

  useEffect(() => {
    if (!base || !metaUrl) return;

    const pollMeta = async () => {
      try {
        const res = await fetch(metaUrl, {
          credentials: "include",
          headers: authHeaders(),
          cache: "no-store",
        });

        const data = (await res.json()) as CameraMeta;

        if (!mountedRef.current) return;

        if (!data?.available) {
          setOk(false);
          setStatusText("Waiting for camera frame...");
          return;
        }

        const isFresh =
          typeof data.updated_at === "number"
            ? Date.now() / 1000 - data.updated_at < 3
            : false;

        if (data.mode === "detection") {
          setStatusText(isFresh ? "Detection mode active" : "Detection paused");
        } else {
          setStatusText(isFresh ? "Raw mode active" : "Raw paused");
        }

        if (typeof data.mode === "string" && data.mode !== mode) {
          setMode(data.mode);
        }

        setMetaTick((n) => n + 1);
      } catch {
        if (!mountedRef.current) return;
        setOk(false);
        setStatusText("Camera disconnected");
      }
    };

    pollMeta();
    metaTimerRef.current = window.setInterval(pollMeta, 1000);

    return () => {
      if (metaTimerRef.current) window.clearInterval(metaTimerRef.current);
    };
  }, [base, metaUrl, mode, token]);

  useEffect(() => {
    if (frameSrc) {
      loadNextFrame(frameSrc);
    }
  }, [frameSrc]);

  if (!API_BASE) {
    return (
      <div className="cam-card">
        <div className="cam-card-header">
          <div className="cam-title">Live Camera Feed</div>
          <div className="cam-status bad">● Missing VITE_CAMERA_API_BASE</div>
        </div>
        <div className="cam-help">Set VITE_CAMERA_API_BASE in your frontend env.</div>
      </div>
    );
  }

  return (
    <div className="cam-card">
      <div className="cam-card-header">
        <div className="cam-title">Live Camera Feed</div>

        <div className="cam-toolbar">
          <div className="cam-status-text">{statusText}</div>

          <div className={`cam-status ${ok ? "good" : "bad"}`}>
            ● {ok ? "Connected" : "Disconnected"}
          </div>

          <button
            onClick={() => setCameraMode("raw")}
            disabled={busy || mode === "raw"}
            className={`cam-btn ${mode === "raw" ? "active" : ""}`}
          >
            Raw
          </button>

          <button
            onClick={() => setCameraMode("detection")}
            disabled={busy || mode === "detection"}
            className={`cam-btn ${mode === "detection" ? "active" : ""}`}
          >
            Detection
          </button>

          <button
            onClick={() => loadNextFrame(
              `${base}/camera/latest?device_id=${encodeURIComponent(
                DEVICE_ID
              )}&mode=${encodeURIComponent(mode)}&t=${Date.now()}`
            )}
            disabled={busy}
            className="cam-btn"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="cam-frame">
        {displaySrc ? (
          <img
            className="cam-img"
            src={displaySrc}
            alt="Camera feed"
            draggable={false}
          />
        ) : (
          <div className="cam-placeholder">
            <div className="cam-placeholder-title">Waiting for camera frame...</div>
            <div className="cam-placeholder-subtitle">
              The Jetson camera is starting up.
            </div>
          </div>
        )}
      </div>

      {err && <div className="cam-error">{err}</div>}
    </div>
  );
}