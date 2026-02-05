import os
import time
import json
import base64
import hmac
import hashlib
from pathlib import Path
from typing import Dict, Any

import cv2
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env from Website/.env (one directory above /backend)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

APP_HOST = os.getenv("CAMERA_API_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("CAMERA_API_PORT", "9000"))

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
ALLOWED_IPS = {ip.strip() for ip in os.getenv("ALLOWED_IPS", "").split(",") if ip.strip()}

# Camera security token (for camera endpoints)
API_TOKEN = os.getenv("API_TOKEN", "")

# Auth settings (optional / future)
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")
AUTH_TOKEN_TTL = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))
AUTH_ALLOWED_DOMAINS = [d.strip().lower() for d in os.getenv("AUTH_ALLOWED_DOMAINS", "tamu.edu").split(",") if d.strip()]

# Camera settings
CAMERA_INDEX = os.getenv("CAMERA_INDEX", "0")
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "30"))
CAMERA_JPEG_QUALITY = int(os.getenv("CAMERA_JPEG_QUALITY", "70"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "720"))
CAMERA_USE_DSHOW = os.getenv("CAMERA_USE_DSHOW", "1") == "1"  # Windows only

# ---------------------------
# Helpers
# ---------------------------

def get_client_ip(request: Request) -> str:
    return request.client.host

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

    raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------
# Camera
# ---------------------------

def open_camera():
    src = CAMERA_INDEX
    if isinstance(src, str) and src.isdigit():
        src = int(src)

    # On Windows, CAP_DSHOW helps a lot. On Jetson/Linux, just use cv2.VideoCapture(src).
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
# FastAPI
# ---------------------------

app = FastAPI()

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/camera/stream")
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

                # throttle
                time.sleep(frame_delay)
        finally:
            cap.release()

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")
