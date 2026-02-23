import os
import time
import random
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException, Response
from pydantic import BaseModel
from dotenv import load_dotenv

from otp_store import OTPStore, hash_code
from security_tokens import mint_app_token
from aura_db import init_db, ta_is_enabled

# Local dev only
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

init_db()

# SMTP settings
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

# Student OTP settings
STUDENT_OTP_TTL_SECONDS = int(os.getenv("STUDENT_OTP_TTL_SECONDS", "300"))
STUDENT_MAX_OTP_ATTEMPTS = int(os.getenv("STUDENT_MAX_OTP_ATTEMPTS", "5"))

# Simple IP rate limit
STUDENT_LOGIN_RATE_WINDOW = int(os.getenv("STUDENT_LOGIN_RATE_WINDOW", "300"))
STUDENT_LOGIN_RATE_MAX = int(os.getenv("STUDENT_LOGIN_RATE_MAX", "20"))

# Cookie settings (optional convenience)
COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "aura_token")
COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "")

router = APIRouter(prefix="/auth/student", tags=["student-auth"])
otp_store = OTPStore(prefix="studentotp")

class StudentStartRequest(BaseModel):
    email: str

class StudentVerifyRequest(BaseModel):
    email: str
    otp: str

_RATE: Dict[str, Dict[str, Any]] = {}

def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _rate_limit_or_429(ip: str):
    now = int(time.time())
    rec = _RATE.get(ip)
    if not rec or now - rec["start"] >= STUDENT_LOGIN_RATE_WINDOW:
        _RATE[ip] = {"start": now, "count": 1}
        return
    rec["count"] += 1
    if rec["count"] > STUDENT_LOGIN_RATE_MAX:
        raise HTTPException(status_code=429, detail="Too many requests")

def _is_tamu(email: str) -> bool:
    return (email or "").strip().lower().endswith("@tamu.edu")

def _send_otp_email(to_email: str, code: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        raise HTTPException(status_code=500, detail="SMTP not configured")

    msg = EmailMessage()
    msg["Subject"] = "AURA Student Login Code"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Your AURA student login code is: {code}\n\n"
        f"This code expires in {max(1, STUDENT_OTP_TTL_SECONDS//60)} minutes.\n"
        f"If you did not request this, ignore this email."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

def _should_secure_cookie(request: Request) -> bool:
    env = (os.getenv("ENV", "") or "").lower()
    if env in ("prod", "production"):
        return True
    return request.url.scheme == "https"

@router.post("/start")
async def start(data: StudentStartRequest, request: Request):
    ip = _client_ip(request)
    _rate_limit_or_429(ip)

    email = (data.email or "").strip().lower()
    if not email or "@" not in email or not _is_tamu(email):
        raise HTTPException(status_code=400, detail="Student email must end with @tamu.edu")

    code = f"{random.randint(100000, 999999)}"
    otp_store.set(email=email, code=code, ttl_seconds=STUDENT_OTP_TTL_SECONDS)
    _send_otp_email(email, code)

    return {"message": "OTP sent", "otp_expires_in": STUDENT_OTP_TTL_SECONDS}

@router.post("/verify")
async def verify(data: StudentVerifyRequest, request: Request, response: Response):
    email = (data.email or "").strip().lower()
    otp = (data.otp or "").strip()

    invalid = HTTPException(status_code=401, detail="Invalid code")

    if not email or "@" not in email or not _is_tamu(email) or not otp:
        raise invalid

    rec = otp_store.get(email)
    if not rec:
        raise invalid

    if int(rec.get("expires", 0)) and time.time() > int(rec["expires"]):
        otp_store.delete(email)
        raise invalid

    attempts = otp_store.incr_attempts(email)
    if attempts > STUDENT_MAX_OTP_ATTEMPTS:
        otp_store.delete(email)
        raise HTTPException(status_code=429, detail="Too many attempts")

    if hash_code(otp) != rec.get("otp_hash"):
        raise invalid

    otp_store.delete(email)

    # ✅ role escalation via DB
    role = "ta" if ta_is_enabled(email) else "student"

    result = mint_app_token(email=email, role=role)
    token = result["token"]

    secure_cookie = _should_secure_cookie(request)
    cookie_kwargs: Dict[str, Any] = {}
    if COOKIE_DOMAIN.strip():
        cookie_kwargs["domain"] = COOKIE_DOMAIN.strip()

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure_cookie,
        samesite=COOKIE_SAMESITE,
        max_age=result["expires_in"],
        **cookie_kwargs,
    )

    return {"token": token, "user": result["user"], "expires_in": result["expires_in"]}