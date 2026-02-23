import os
import time
import threading
from pathlib import Path
from typing import Optional, Dict

import cv2
from dotenv import load_dotenv
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, Response

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

ALLOWED_IPS = {ip.strip() for ip in os.getenv("ALLOWED_IPS", "").split(",") if ip.strip()}
API_TOKEN = os.getenv("API_TOKEN", "")

# CORS for MJPEG <img> + canvas snapshot
# Must be explicit origins (NOT *) for best compatibility.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

CAMERA_INDEX = os.getenv("CAMERA_INDEX", "0")
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "30"))
CAMERA_JPEG_QUALITY = int(os.getenv("CAMERA_JPEG_QUALITY", "70"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "720"))
CAMERA_USE_DSHOW = os.getenv("CAMERA_USE_DSHOW", "1") == "1"

router = APIRouter(prefix="/camera", tags=["camera"])


def get_client_ip(request: Request) -> str:
    # If you later sit behind a proxy, you may want to respect X-Forwarded-For here too.
    return request.client.host if request.client else "unknown"


def require_ip_allowlist(request: Request):
    if not ALLOWED_IPS:
        return
    ip = get_client_ip(request)
    if ip not in ALLOWED_IPS:
        raise HTTPException(status_code=403, detail=f"IP not allowed: {ip}")


def require_camera_token(request: Request):
    if not API_TOKEN:
        raise HTTPException(status_code=500, detail="Server missing API_TOKEN")

    auth = request.headers.get("authorization", "")
    if auth == f"Bearer {API_TOKEN}":
        return

    token_q = request.query_params.get("token", "")
    if token_q == API_TOKEN:
        return

    raise HTTPException(status_code=401, detail="Invalid camera token")


def _camera_src():
    src = CAMERA_INDEX
    if isinstance(src, str) and src.isdigit():
        return int(src)
    return src


def _open_camera_once():
    src = _camera_src()
    if CAMERA_USE_DSHOW:
        cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(src)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera: {CAMERA_INDEX}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    time.sleep(0.10)
    return cap


# ============================
# Shared camera worker state
# ============================
_frame_lock = threading.Lock()
_last_jpg: Optional[bytes] = None
_last_frame_ts: float = 0.0

_worker_started = False
_worker_lock = threading.Lock()


def _camera_worker():
    global _last_jpg, _last_frame_ts

    cap = None
    backoff = 0.2

    while True:
        try:
            if cap is None or not cap.isOpened():
                cap = _open_camera_once()
                backoff = 0.2

            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.02)
                continue

            ok, jpg = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), CAMERA_JPEG_QUALITY],
            )
            if not ok:
                continue

            with _frame_lock:
                _last_jpg = jpg.tobytes()
                _last_frame_ts = time.time()

            time.sleep(1.0 / max(CAMERA_FPS, 1))

        except Exception:
            # Important on Windows: release and retry with backoff
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
            cap = None
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 2.0)


def _ensure_worker():
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_camera_worker, daemon=True)
        t.start()
        _worker_started = True


def _cors_headers_for_stream(request: Request) -> Dict[str, str]:
    """
    These headers are crucial so the MJPEG <img> can be drawn onto a canvas.
    - We DO NOT return '*' because that can break when credentials are involved.
    - We reflect only allowed origins.
    """
    origin = request.headers.get("origin", "")
    headers: Dict[str, str] = {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
        # Helps with some browser security models when embedding cross-origin.
        "Cross-Origin-Resource-Policy": "cross-origin",
        "Vary": "Origin",
    }

    if not origin:
        return headers

    if ALLOWED_ORIGINS and origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    # If origin not allowed, we simply omit ACAO and browser will block canvas draw.

    return headers


@router.options("/stream")
async def stream_options(request: Request):
    # Some environments/proxies do preflight-like behavior; safe to include.
    headers = _cors_headers_for_stream(request)
    return Response(status_code=204, headers=headers)


@router.get("/stream")
async def stream(request: Request):
    require_ip_allowlist(request)
    require_camera_token(request)
    _ensure_worker()

    headers = _cors_headers_for_stream(request)

    async def gen():
        # If worker hasn't produced frames yet, give it a moment
        start = time.time()
        while True:
            if await request.is_disconnected():
                return
            with _frame_lock:
                ready = _last_jpg is not None
            if ready:
                break
            if time.time() - start > 3.0:
                break
            time.sleep(0.05)

        # Stream latest frame repeatedly
        while True:
            if await request.is_disconnected():
                return

            with _frame_lock:
                jpg = _last_jpg
                ts = _last_frame_ts

            if jpg is None:
                time.sleep(0.05)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-store\r\n\r\n"
                + jpg
                + b"\r\n"
            )

            time.sleep(1.0 / max(CAMERA_FPS, 1))

    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=headers,
    )