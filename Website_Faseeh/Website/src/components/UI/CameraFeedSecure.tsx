import { useMemo } from "react";

const BASE = import.meta.env.VITE_CAMERA_API_BASE;
const TOKEN = import.meta.env.VITE_CAMERA_STREAM_TOKEN; // public (dev only)

export default function CameraFeedSecure() {
  const src = useMemo(() => {
    // MJPEG stream in <img> cannot send Authorization header, so we use ?token=
    const url = new URL(`${BASE}/camera/stream`);
    if (TOKEN) url.searchParams.set("token", TOKEN);
    url.searchParams.set("t", String(Date.now())); // cache-bust on reload
    return url.toString();
  }, []);

  return (
    <div className="camera-wrap">
      <div className="camera-frame">
        <img className="camera-img" src={src} alt="Camera stream" />
      </div>
    </div>
  );
}
