import os
import time
import json
import base64
import hmac
import hashlib
import random
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Optional IP allowlist
ALLOWED_IPS = {ip.strip() for ip in os.getenv("ALLOWED_IPS", "").split(",") if ip.strip()}

# Token settings
AUTH_SECRET = os.getenv("AUTH_SECRET", "")
AUTH_TOKEN_TTL = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))

# SMTP settings (Gmail App Password)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

# Admin user store
ADMIN_USERS_PATH = Path(__file__).resolve().parent / "admin_users.json"

router = APIRouter(prefix="/auth/admin", tags=["admin-auth"])


class AdminLoginRequest(BaseModel):
    email: str
    password: str

class AdminVerifyRequest(BaseModel):
    email: str
    otp: str


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
# PBKDF2 password verify
# stored format: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
# ---------------------------
def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False

        iterations = int(iters)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(hash_b64)

        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ---------------------------
# Auth token (HMAC signed)
# ---------------------------
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def sign_token(payload: Dict[str, Any]) -> str:
    if not AUTH_SECRET:
        raise HTTPException(status_code=500, detail="Server missing AUTH_SECRET")

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
        if time.time() > int(payload.get("exp", 0)):
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
    return verify_token(auth.replace("Bearer ", "", 1).strip())


# ---------------------------
# Admins loader
# ---------------------------
def load_admins() -> Dict[str, str]:
    """
    Returns dict: { email_lower: password_hash_string }
    """
    if not ADMIN_USERS_PATH.exists():
        raise HTTPException(status_code=500, detail="admin_users.json missing")

    with open(ADMIN_USERS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    out: Dict[str, str] = {}
    for a in data.get("admins", []):
        email = (a.get("email") or "").strip().lower()
        ph = (a.get("password_hash") or "").strip()
        if email and ph:
            out[email] = ph
    return out


# ---------------------------
# Email OTP
# ---------------------------
def send_otp_email(to_email: str, code: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        raise HTTPException(status_code=500, detail="SMTP not configured (set SMTP_* in .env)")

    msg = EmailMessage()
    msg["Subject"] = "ARUA Admin Login Code"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Your ARUA admin login code is: {code}\n\n"
        f"This code expires in 5 minutes.\n"
        f"If you did not request this, ignore this email."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


# In-memory OTP store
OTP_STORE: Dict[str, Dict[str, Any]] = {}  # email -> {code, expires, attempts}


@router.post("/login")
async def login(data: AdminLoginRequest, request: Request):
    require_ip_allowlist(request)

    email = data.email.strip().lower()
    password = data.password.strip()

    admins = load_admins()

    if email not in admins:
        raise HTTPException(status_code=403, detail="Not an admin email")

    # PBKDF2 verify (no passlib/bcrypt)
    if not verify_password(password, admins[email]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    code = f"{random.randint(100000, 999999)}"
    expires = int(time.time()) + 300  # 5 minutes

    OTP_STORE[email] = {"code": code, "expires": expires, "attempts": 0}

    send_otp_email(email, code)

    return {"message": "OTP sent to email", "otp_expires_in": 300}


@router.post("/verify")
async def verify(data: AdminVerifyRequest, request: Request):
    require_ip_allowlist(request)

    email = data.email.strip().lower()
    otp = data.otp.strip()

    rec = OTP_STORE.get(email)
    if not rec:
        raise HTTPException(status_code=400, detail="No OTP pending")

    if time.time() > rec["expires"]:
        OTP_STORE.pop(email, None)
        raise HTTPException(status_code=401, detail="OTP expired")

    rec["attempts"] += 1
    if rec["attempts"] > 5:
        OTP_STORE.pop(email, None)
        raise HTTPException(status_code=429, detail="Too many attempts")

    if otp != rec["code"]:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    OTP_STORE.pop(email, None)

    now = int(time.time())
    token = sign_token({"sub": email, "role": "admin", "iat": now, "exp": now + AUTH_TOKEN_TTL})
    return {"token": token, "user": {"email": email, "role": "admin"}, "expires_in": AUTH_TOKEN_TTL}


@router.get("/me")
def me(request: Request):
    require_ip_allowlist(request)
    payload = require_auth(request)
    return {"user": {"email": payload.get("sub"), "role": payload.get("role")}, "exp": payload.get("exp")}
