import { useMemo, useState } from "react";
import "../../styles/cameraFeed.css";

const RAW_BASE = import.meta.env.VITE_CAMERA_API_BASE as string | undefined;
const TOKEN = import.meta.env.VITE_CAMERA_STREAM_TOKEN as string | undefined;

export default function CameraFeedSecure() {
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const src = useMemo(() => {
    const base = (RAW_BASE || "").replace(/\/+$/, "");
    if (!base) return "";
    const token = TOKEN || "";
    const qs =
      `token=${encodeURIComponent(token)}` +
      `&t=${Date.now()}`; // cache bust
    return `${base}/camera/stream?${qs}`;
  }, []);

  // If env is missing, don't crash — show a helpful message
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
            }}
          />
        ) : (
          <div className="cam-help">Stream URL is empty.</div>
        )}
      </div>

      {err && <div className="cam-error">{err}</div>}
    </div>
  );
}