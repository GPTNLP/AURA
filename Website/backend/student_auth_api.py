# backend/student_auth_api.py
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

from security import require_ip_allowlist, domain_allowed, resolve_current_role
from security_tokens import mint_app_token
from otp_store import OTPStore, hash_code

# Local dev only
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

# SMTP settings
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

STUDENT_OTP_TTL_SECONDS = int(os.getenv("STUDENT_OTP_TTL_SECONDS", "300"))
STUDENT_MAX_OTP_ATTEMPTS = int(os.getenv("STUDENT_MAX_OTP_ATTEMPTS", "6"))

COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "aura_token")
COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "")

router = APIRouter(prefix="/auth/student", tags=["student-auth"])
otp_store = OTPStore(prefix="studentotp")


class StudentStartReq(BaseModel):
    email: str


class StudentVerifyReq(BaseModel):
    email: str
    otp: str


def _should_secure_cookie(request: Request) -> bool:
    env = (os.getenv("ENV", "") or "").lower()
    if env in ("prod", "production"):
        return True
    return request.url.scheme == "https"


def _send_otp_email(to_email: str, code: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        raise HTTPException(status_code=500, detail="SMTP not configured")

    msg = EmailMessage()
    msg["Subject"] = "AURA Student Login Code"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Your AURA login code is: {code}\n\n"
        f"This code expires in {max(1, STUDENT_OTP_TTL_SECONDS // 60)} minutes.\n"
        f"If you did not request this, ignore this email."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def _portal_hints(email: str) -> Dict[str, Any]:
    role = resolve_current_role(email)

    has_admin_access = role == "admin"
    has_ta_access = role == "ta"

    notice = None
    if has_admin_access:
        notice = "This account also has admin access. Use Admin Login for full portal access."
    elif has_ta_access:
        notice = "This account also has TA access. Use TA Login for TA tools."

    return {
        "has_admin_access": has_admin_access,
        "has_ta_access": has_ta_access,
        "notice": notice,
    }


@router.post("/start")
async def start(data: StudentStartReq, request: Request):
    require_ip_allowlist(request)

    email = (data.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Enter your TAMU email")

    if not domain_allowed(email):
        raise HTTPException(status_code=403, detail="Only @tamu.edu emails are allowed")

    code = f"{random.randint(100000, 999999)}"
    otp_store.set(email=email, code=code, ttl_seconds=STUDENT_OTP_TTL_SECONDS)
    _send_otp_email(email, code)

    return {
        "message": "OTP sent",
        "otp_expires_in": STUDENT_OTP_TTL_SECONDS,
        **_portal_hints(email),
    }


@router.post("/verify")
async def verify(data: StudentVerifyReq, request: Request, response: Response):
    require_ip_allowlist(request)

    email = (data.email or "").strip().lower()
    otp = (data.otp or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Enter your TAMU email")

    if not domain_allowed(email):
        raise HTTPException(status_code=403, detail="Only @tamu.edu emails are allowed")

    rec = otp_store.get(email)
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid code")

    if int(rec.get("expires", 0) or 0) and time.time() > int(rec["expires"]):
        otp_store.delete(email)
        raise HTTPException(status_code=401, detail="Invalid code")

    attempts = otp_store.incr_attempts(email)
    if attempts > STUDENT_MAX_OTP_ATTEMPTS:
        otp_store.delete(email)
        raise HTTPException(status_code=429, detail="Too many attempts")

    if hash_code(otp) != rec.get("otp_hash"):
        raise HTTPException(status_code=401, detail="Invalid code")

    otp_store.delete(email)

    result = mint_app_token(email=email, role="student")
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

    return {
        "token": token,
        "user": result["user"],
        "expires_in": result["expires_in"],
        **_portal_hints(email),
    }