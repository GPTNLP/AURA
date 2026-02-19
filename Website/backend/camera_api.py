import os
import time
from pathlib import Path

import cv2
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

# Load .env from Website/.env (one directory above /backend)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Allowlist + camera token
ALLOWED_IPS = {ip.strip() for ip in os.getenv("ALLOWED_IPS", "").split(",") if ip.strip()}
API_TOKEN = os.getenv("API_TOKEN", "")

# Camera settings
CAMERA_INDEX = os.getenv("CAMERA_INDEX", "0")
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "30"))
CAMERA_JPEG_QUALITY = int(os.getenv("CAMERA_JPEG_QUALITY", "70"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "720"))
CAMERA_USE_DSHOW = os.getenv("CAMERA_USE_DSHOW", "1") == "1"  # Windows only

router = APIRouter(prefix="/camera", tags=["camera"])


# ---------------------------
# IP allowlist
# ---------------------------
def get_client_ip(request: Request) -> str:
    return request.client.host

def require_ip_allowlist(request: Request):
    if not ALLOWED_IPS:
        return
    ip = get_client_ip(request)
    if ip not in ALLOWED_IPS:
        raise HTTPException(status_code=403, detail=f"IP not allowed: {ip}")


# ---------------------------
# Camera token (header OR ?token=)
# ---------------------------
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


# ---------------------------
# Camera open
# ---------------------------
def open_camera():
    src = CAMERA_INDEX
    if isinstance(src, str) and src.isdigit():
        src = int(src)

    if CAMERA_USE_DSHOW:
        cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(src)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera: {CAMERA_INDEX}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)

    time.sleep(0.15)
    return cap


# ---------------------------
# Camera stream (token-gated)
# ---------------------------
@router.get("/stream")
def stream(request: Request):
    require_ip_allowlist(request)
    require_camera_token(request)

    def gen():
        cap = open_camera()
        frame_delay = 1.0 / max(CAMERA_FPS, 1)

        try:
            while True:
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

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
                )
                time.sleep(frame_delay)
        finally:
            cap.release()

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")
