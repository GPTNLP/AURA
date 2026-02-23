import { useEffect, useRef, useState } from "react";
import "../../styles/cameraFeed.css";
import { useAuth } from "../../services/authService";

const RAW_BASE = import.meta.env.VITE_CAMERA_API_BASE as string | undefined;
const TOKEN = import.meta.env.VITE_CAMERA_STREAM_TOKEN as string | undefined;

type DetectBox = { x1: number; y1: number; x2: number; y2: number };
type DetectItem = {
  label: string;
  class_id: number;
  confidence: number;
  box: DetectBox;
  resistor_value?: { label: string; class_id: number; confidence: number };
};
type DetectResp = { detections: DetectItem[]; width: number; height: number };

export default function CameraFeedSecure() {
  const { token } = useAuth();

  const [ok, setOk] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [src, setSrc] = useState("");

  const [detecting, setDetecting] = useState(false);
  const [detections, setDetections] = useState<DetectItem[]>([]);
  const [detectErr, setDetectErr] = useState<string | null>(null);

  const imgRef = useRef<HTMLImageElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);

  const timerRef = useRef<number | null>(null);
  const mountedRef = useRef(false);

  const makeUrl = () => {
    const base = (RAW_BASE || "").replace(/\/+$/, "");
    if (!base) return "";
    const t = TOKEN || "";
    return `${base}/camera/stream?token=${encodeURIComponent(t)}&t=${Date.now()}&r=${Math.random()}`;
  };

  const hardClose = () => setSrc("");

  const scheduleRefresh = (delayMs = 120) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);

    timerRef.current = window.setTimeout(() => {
      if (!mountedRef.current) return;
      setOk(false);
      setErr(null);
      hardClose();
      window.setTimeout(() => {
        if (!mountedRef.current) return;
        setSrc(makeUrl());
      }, 40);
    }, delayMs);
  };

  // Resize overlay canvas to match displayed <img>
  const syncOverlaySize = () => {
    const img = imgRef.current;
    const cvs = overlayRef.current;
    if (!img || !cvs) return;

    const w = img.clientWidth;
    const h = img.clientHeight;
    if (!w || !h) return;

    // match physical pixels to avoid blur
    const dpr = window.devicePixelRatio || 1;
    cvs.width = Math.round(w * dpr);
    cvs.height = Math.round(h * dpr);
    cvs.style.width = `${w}px`;
    cvs.style.height = `${h}px`;

    const ctx = cvs.getContext("2d");
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  const drawDetections = (items: DetectItem[]) => {
    const img = imgRef.current;
    const cvs = overlayRef.current;
    if (!img || !cvs) return;

    syncOverlaySize();

    const ctx = cvs.getContext("2d");
    if (!ctx) return;

    const dispW = img.clientWidth;
    const dispH = img.clientHeight;

    // We need to map model coords (based on decoded image) to displayed pixels.
    // We’ll estimate using the underlying natural size.
    const natW = img.naturalWidth || dispW;
    const natH = img.naturalHeight || dispH;

    const sx = dispW / natW;
    const sy = dispH / natH;

    ctx.clearRect(0, 0, dispW, dispH);

    // Basic box styling (no theme colors required)
    ctx.lineWidth = 2;
    ctx.font = "12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace";

    for (const d of items) {
      const x = d.box.x1 * sx;
      const y = d.box.y1 * sy;
      const w = (d.box.x2 - d.box.x1) * sx;
      const h = (d.box.y2 - d.box.y1) * sy;

      // box
      ctx.strokeStyle = "rgba(0, 255, 0, 0.95)";
      ctx.strokeRect(x, y, w, h);

      // label
      const baseLabel = `${d.label} ${(d.confidence * 100).toFixed(0)}%`;
      const rv = d.resistor_value?.label ? ` • ${d.resistor_value.label}` : "";
      const text = baseLabel + rv;

      const pad = 4;
      const tw = ctx.measureText(text).width;
      const th = 14;

      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fillRect(x, Math.max(0, y - th - 4), tw + pad * 2, th + 4);

      ctx.fillStyle = "white";
      ctx.fillText(text, x + pad, Math.max(12, y - 8));
    }
  };

  const clearOverlay = () => {
    const img = imgRef.current;
    const cvs = overlayRef.current;
    if (!img || !cvs) return;
    const ctx = cvs.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, cvs.width, cvs.height);
  };

  const captureFrameBlob = async (): Promise<Blob> => {
    const img = imgRef.current;
    if (!img) throw new Error("Camera image not ready yet.");

    // Draw current MJPEG frame into a canvas
    const c = document.createElement("canvas");
    const w = img.naturalWidth || 1280;
    const h = img.naturalHeight || 720;
    c.width = w;
    c.height = h;

    const ctx = c.getContext("2d");
    if (!ctx) throw new Error("Canvas not supported");

    ctx.drawImage(img, 0, 0, w, h);

    const blob: Blob | null = await new Promise((resolve) =>
      c.toBlob((b) => resolve(b), "image/jpeg", 0.9)
    );

    if (!blob) throw new Error("Failed to capture frame");
    return blob;
  };

  const runDetect = async () => {
    if (!RAW_BASE) return;
    if (detecting) return;

    setDetectErr(null);
    setDetecting(true);

    try {
      const blob = await captureFrameBlob();
      const fd = new FormData();
      fd.append("file", blob, "frame.jpg");

      const base = RAW_BASE.replace(/\/+$/, "");
      const res = await fetch(`${base}/api/detect/predict`, {
        method: "POST",
        body: fd,
        credentials: "include",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });

      const data = (await res.json().catch(() => null)) as DetectResp | null;
      if (!res.ok) {
        const msg = (data as any)?.detail || `Detect failed (${res.status})`;
        throw new Error(msg);
      }

      const items = Array.isArray(data?.detections) ? data!.detections : [];
      setDetections(items);
      drawDetections(items);
    } catch (e: any) {
      setDetectErr(e?.message || "Detection failed");
      setDetections([]);
      clearOverlay();
    } finally {
      setDetecting(false);
    }
  };

  // Mount/unmount lifecycle
  useEffect(() => {
    mountedRef.current = true;
    scheduleRefresh(0);

    const onResize = () => {
      syncOverlaySize();
      drawDetections(detections);
    };

    window.addEventListener("resize", onResize);

    return () => {
      mountedRef.current = false;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      hardClose();
      window.removeEventListener("resize", onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refresh when user returns
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
          Add <code>VITE_CAMERA_API_BASE=http://127.0.0.1:9000</code> to your Website/.env and restart{" "}
          <code>npm run dev</code>.
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
        </div>

        <button
          onClick={runDetect}
          disabled={!ok || detecting}
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid var(--card-border)",
            background: "var(--card-bg)",
            fontWeight: 900,
            cursor: !ok || detecting ? "not-allowed" : "pointer",
            opacity: !ok || detecting ? 0.6 : 1,
          }}
          title="Capture a frame and run YOLO detection"
        >
          {detecting ? "Detecting…" : "Detect"}
        </button>

        <button
          onClick={() => {
            setDetections([]);
            clearOverlay();
          }}
          disabled={detections.length === 0}
          style={{
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid var(--card-border)",
            background: "var(--card-bg)",
            fontWeight: 900,
            cursor: detections.length === 0 ? "not-allowed" : "pointer",
            opacity: detections.length === 0 ? 0.6 : 1,
          }}
          title="Clear overlay"
        >
          Clear
        </button>
      </div>

      <div className="cam-frame" style={{ position: "relative" }}>
        {src ? (
          <>
            <img
              ref={imgRef}
              className="cam-img"
              src={src}
              alt="Camera stream"
              crossOrigin="anonymous"
              onLoad={() => {
                setOk(true);
                setErr(null);
                syncOverlaySize();
                drawDetections(detections);
              }}
              onError={() => {
                setOk(false);
                setErr("Stream failed (check backend /camera/stream)");
                scheduleRefresh(500);
              }}
            />
            <canvas
              ref={overlayRef}
              style={{
                position: "absolute",
                inset: 0,
                pointerEvents: "none",
              }}
            />
          </>
        ) : (
          <div className="cam-help">Connecting...</div>
        )}
      </div>

      {err && <div className="cam-error">{err}</div>}
      {detectErr && <div className="cam-error">{detectErr}</div>}
    </div>
  );
}