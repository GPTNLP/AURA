# backend/security.py
import os
from typing import Dict, Any, Set
from fastapi import Request, HTTPException

from config import ALLOWED_IPS, API_TOKEN, AUTH_ALLOWED_DOMAINS
from security_tokens import verify_token

# ---------------------------
# Client IP (Azure-friendly)
# ---------------------------
def get_client_ip(request: Request) -> str:
    # Trust X-Forwarded-For only if you are behind Azure / reverse proxy
    # App Service sets X-Forwarded-For.
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def require_ip_allowlist(request: Request):
    # If ALLOWED_IPS empty -> allow all
    if not ALLOWED_IPS:
        return
    ip = get_client_ip(request)
    if ip not in ALLOWED_IPS:
        raise HTTPException(status_code=403, detail="IP not allowed")

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
# Auth token (cookie preferred, Bearer supported)
# ---------------------------
def _get_auth_token_from_request(request: Request) -> str:
    # Prefer secure httpOnly cookie
    COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "aura_token")
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token

    # Fall back to Authorization header for tools / dev
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth.replace("Bearer ", "", 1).strip()

    return ""

def require_auth(request: Request) -> Dict[str, Any]:
    token = _get_auth_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        return verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------
# Email domain restriction
# ---------------------------
def domain_allowed(email: str) -> bool:
    email = (email or "").strip().lower()
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1]
    return domain in set(AUTH_ALLOWED_DOMAINS or [])