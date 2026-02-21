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

from security_tokens import mint_app_token
from security import require_ip_allowlist, domain_allowed
from otp_store import OTPStore, hash_code

# Local dev only
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

STUDENT_OTP_TTL_SECONDS = int(os.getenv("STUDENT_OTP_TTL_SECONDS", "300"))
STUDENT_MAX_OTP_ATTEMPTS = int(os.getenv("STUDENT_MAX_OTP_ATTEMPTS", "5"))

# Rate limit student OTP starts (per IP)
STUDENT_RATE_WINDOW = int(os.getenv("STUDENT_RATE_WINDOW", "300"))
STUDENT_RATE_MAX = int(os.getenv("STUDENT_RATE_MAX", "20"))

router = APIRouter(prefix="/auth/student", tags=["student-auth"])
otp_store = OTPStore(prefix="studentotp")

_RATE: Dict[str, Dict[str, Any]] = {}

class StudentStartRequest(BaseModel):
    email: str

class StudentVerifyRequest(BaseModel):
    email: str
    otp: str

def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def _rate_limit_or_429(ip: str):
    now = int(time.time())
    rec = _RATE.get(ip)
    if not rec or now - rec["start"] >= STUDENT_RATE_WINDOW:
        _RATE[ip] = {"start": now, "count": 1}
        return
    rec["count"] += 1
    if rec["count"] > STUDENT_RATE_MAX:
        raise HTTPException(status_code=429, detail="Too many requests")

def _send_student_otp_email(to_email: str, code: str):
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

@router.post("/start")
async def start(data: StudentStartRequest, request: Request):
    require_ip_allowlist(request)

    ip = _client_ip(request)
    _rate_limit_or_429(ip)

    email = (data.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email")

    if not domain_allowed(email):
        raise HTTPException(status_code=403, detail="Only allowed email domains are permitted")

    code = f"{random.randint(100000, 999999)}"
    otp_store.set(email=email, code=code, ttl_seconds=STUDENT_OTP_TTL_SECONDS)
    _send_student_otp_email(email, code)

    return {"message": "OTP sent", "otp_expires_in": STUDENT_OTP_TTL_SECONDS}

@router.post("/verify")
async def verify(data: StudentVerifyRequest, request: Request, response: Response):
    require_ip_allowlist(request)

    email = (data.email or "").strip().lower()
    otp = (data.otp or "").strip()

    invalid = HTTPException(status_code=401, detail="Invalid code")

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

    result = mint_app_token(email=email, role="student")

    response.set_cookie(
        key="aura_token",
        value=result["token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=result["expires_in"],
    )

    return {"user": result["user"], "expires_in": result["expires_in"]}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("aura_token")
    return {"ok": True}