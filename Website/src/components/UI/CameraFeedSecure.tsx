import { useEffect, useRef, useState } from "react";
import "../../styles/cameraFeed.css";

const RAW_BASE = import.meta.env.VITE_CAMERA_API_BASE as string | undefined;
const TOKEN = import.meta.env.VITE_CAMERA_STREAM_TOKEN as string | undefined;

export default function CameraFeedSecure() {
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [src, setSrc] = useState("");

  const timerRef = useRef<number | null>(null);
  const mountedRef = useRef(false);

  const makeUrl = () => {
    const base = (RAW_BASE || "").replace(/\/+$/, "");
    if (!base) return "";
    const token = TOKEN || "";
    return `${base}/camera/stream?token=${encodeURIComponent(token)}&t=${Date.now()}&r=${Math.random()}`;
  };

  const hardClose = () => {
    // Forces browser to drop MJPEG connection
    setSrc("");
  };

  const scheduleRefresh = (delayMs = 120) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);

    timerRef.current = window.setTimeout(() => {
      if (!mountedRef.current) return;
      setOk(false);
      setErr(null);
      hardClose();
      // tiny delay to ensure socket closes before reopening
      window.setTimeout(() => {
        if (!mountedRef.current) return;
        setSrc(makeUrl());
      }, 40);
    }, delayMs);
  };

  // Mount/unmount lifecycle
  useEffect(() => {
    mountedRef.current = true;
    scheduleRefresh(0);

    return () => {
      mountedRef.current = false;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      hardClose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refresh when user returns, but debounce so tab spam doesn't kill it
  useEffect(() => {
    const onFocus = () => scheduleRefresh(250);
    const onVis = () => {
      if (document.visibilityState === "visible") scheduleRefresh(250);
    };

    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVis);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!RAW_BASE) {
    return (
      <div className="cam-card">
        <div className="cam-card-header">
          <div className="cam-title">Live Camera Feed</div>
          <div className="cam-status bad">● Missing VITE_CAMERA_API_BASE</div>
        </div>
        <div className="cam-help">
          Add <code>VITE_CAMERA_API_BASE=http://127.0.0.1:9000</code> to your Website/.env
          and restart <code>npm run dev</code>.
        </div>
      </div>
    );
  }

  return (
    <div className="cam-card">
      <div className="cam-card-header">
        <div className="cam-title">Live Camera Feed</div>
        <div className={`cam-status ${ok ? "good" : "bad"}`}>
          ● {ok ? "Connected" : "Disconnected"}
        </div>
      </div>

      <div className="cam-frame">
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
              setErr("Stream failed (check backend /camera/stream)");
              // auto-retry, but debounced
              scheduleRefresh(500);
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