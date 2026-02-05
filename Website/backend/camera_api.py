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

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
ALLOWED_IPS = {ip.strip() for ip in os.getenv("ALLOWED_IPS", "").split(",") if ip.strip()}

# Camera token (for camera endpoints)
API_TOKEN = os.getenv("API_TOKEN", "")

# Auth settings (website login)
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")
AUTH_TOKEN_TTL = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))
AUTH_ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in os.getenv("AUTH_ALLOWED_DOMAINS", "tamu.edu").split(",")
    if d.strip()
]

# Camera settings
CAMERA_INDEX = os.getenv("CAMERA_INDEX", "0")
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "30"))
CAMERA_JPEG_QUALITY = int(os.getenv("CAMERA_JPEG_QUALITY", "70"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "720"))
CAMERA_USE_DSHOW = os.getenv("CAMERA_USE_DSHOW", "1") == "1"  # Windows only


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
# Auth token (HMAC signed)
# ---------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def sign_token(payload: Dict[str, Any]) -> str:
    if not AUTH_SECRET:
        raise RuntimeError("AUTH_SECRET missing")
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    return f"{_b64url_encode(raw)}.{_b64url_encode(sig)}"

def verify_token(token: str) -> Dict[str, Any]:
    if not AUTH_SECRET:
        raise HTTPException(status_code=500, detail="Server missing AUTH_SECRET")

    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _b64url_decode(raw_b64)
        sig = _b64url_decode(sig_b64)

        expected = hmac.new(AUTH_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=401, detail="Invalid token")

        payload = json.loads(raw.decode("utf-8"))
        exp = int(payload.get("exp", 0))
        if exp and time.time() > exp:
            raise HTTPException(status_code=401, detail="Token expired")

        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_auth(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing auth token")
    token = auth.replace("Bearer ", "", 1).strip()
    return verify_token(token)

def domain_allowed(email: str) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1]
    return domain in AUTH_ALLOWED_DOMAINS


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


# ---------------------------
# Website login (password)
# ---------------------------

@app.post("/auth/login")
async def auth_login(request: Request):
    require_ip_allowlist(request)

    if not AUTH_PASSWORD or not AUTH_SECRET:
        raise HTTPException(status_code=500, detail="Server missing AUTH_PASSWORD or AUTH_SECRET")

    body = await request.json()
    email = (body.get("email") or "").strip()
    password = (body.get("password") or "").strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email + password required")

    if password != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not domain_allowed(email):
        raise HTTPException(status_code=403, detail="Email domain not allowed")

    now = int(time.time())
    payload = {"sub": email, "iat": now, "exp": now + AUTH_TOKEN_TTL}
    token = sign_token(payload)

    return {"token": token, "user": {"email": email}, "expires_in": AUTH_TOKEN_TTL}


@app.get("/auth/me")
def auth_me(request: Request):
    require_ip_allowlist(request)
    payload = require_auth(request)
    return {"user": {"email": payload.get("sub")}, "exp": payload.get("exp")}


# ---------------------------
# Camera stream (still token-gated)
# ---------------------------

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

                ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), CAMERA_JPEG_QUALITY])
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
