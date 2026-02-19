import time
import json
import base64
import hmac
import hashlib
from typing import Dict, Any

from fastapi import Request, HTTPException

from config import ALLOWED_IPS, API_TOKEN, AUTH_SECRET, AUTH_ALLOWED_DOMAINS


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
