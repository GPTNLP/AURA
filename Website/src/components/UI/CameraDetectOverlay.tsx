import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../services/authService";

type Det = {
  label: string;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  spoken_text?: string;
  resistor_value?: string;
};

const API_BASE =
  (import.meta.env.VITE_AUTH_API_BASE as string | undefined) ||
  (import.meta.env.VITE_CAMERA_API_BASE as string | undefined) ||
  "http://127.0.0.1:9000";

export default function CameraDetectOverlay({
  videoRef,
  enabled,
}: {
  videoRef: React.RefObject<HTMLVideoElement>;
  enabled: boolean;
}) {
  const { token } = useAuth();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [last, setLast] = useState<Det[] | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: any = null;

    const loop = async () => {
      if (!enabled) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;

      if (!video || !canvas) {
        timer = setTimeout(loop, 500);
        return;
      }

      const vw = video.videoWidth || 0;
      const vh = video.videoHeight || 0;

      if (vw < 2 || vh < 2) {
        timer = setTimeout(loop, 500);
        return;
      }

      // Match canvas to video
      canvas.width = vw;
      canvas.height = vh;

      // draw frame into an offscreen canvas so we can create a JPEG blob
      const off = document.createElement("canvas");
      off.width = vw;
      off.height = vh;
      const ctxOff = off.getContext("2d");
      if (!ctxOff) {
        timer = setTimeout(loop, 500);
        return;
      }
      ctxOff.drawImage(video, 0, 0, vw, vh);

      const blob: Blob | null = await new Promise((resolve) =>
        off.toBlob(resolve, "image/jpeg", 0.8)
      );

      if (!blob) {
        timer = setTimeout(loop, 500);
        return;
      }

      try {
        const fd = new FormData();
        fd.append("file", blob, "frame.jpg");

        const res = await fetch(`${API_BASE}/api/detect/predict`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          credentials: "include",
          body: fd,
        });

        const data = await res.json().catch(() => null);

        if (!alive) return;

        if (!res.ok) {
          // clear overlay on error
          setLast(null);
        } else {
          setLast(Array.isArray(data?.detections) ? data.detections : []);
        }
      } catch {
        if (!alive) return;
        setLast(null);
      }

      timer = setTimeout(loop, 600); // detection rate (ms)
    };

    loop();

    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [enabled, token, videoRef]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // clear
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!enabled || !last) return;

    // draw boxes
    ctx.lineWidth = 3;
    ctx.font = "16px system-ui";

    for (const d of last) {
      const w = d.x2 - d.x1;
      const h = d.y2 - d.y1;

      ctx.strokeStyle = "rgba(0, 255, 0, 0.9)";
      ctx.strokeRect(d.x1, d.y1, w, h);

      const label = d.spoken_text
        ? `${d.label} • ${d.spoken_text}`
        : `${d.label} • ${(d.confidence * 100).toFixed(0)}%`;

      const tx = d.x1;
      const ty = Math.max(18, d.y1 - 6);

      ctx.fillStyle = "rgba(0,0,0,0.55)";
      const metrics = ctx.measureText(label);
      ctx.fillRect(tx - 4, ty - 16, metrics.width + 8, 20);

      ctx.fillStyle = "white";
      ctx.fillText(label, tx, ty);
    }
  }, [enabled, last]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
    />
  );
}