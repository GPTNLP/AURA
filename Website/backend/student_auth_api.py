import os
import time
import json
import random
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Request, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel

from security_tokens import mint_app_token  # <-- use your mint_app_token helper
from security import require_ip_allowlist, domain_allowed  # <-- uses config AUTH_ALLOWED_DOMAINS

# Load .env from Website/.env (one directory above /backend)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# SMTP settings (Gmail App Password)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

router = APIRouter(prefix="/auth/student", tags=["student-auth"])


class StudentStartRequest(BaseModel):
    email: str


class StudentVerifyRequest(BaseModel):
    email: str
    otp: str


# ---------------------------
# Email OTP
# ---------------------------
def send_student_otp_email(to_email: str, code: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        raise HTTPException(status_code=500, detail="SMTP not configured (set SMTP_* in .env)")

    msg = EmailMessage()
    msg["Subject"] = "AURA Student Login Code"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Your AURA student login code is: {code}\n\n"
        f"This code expires in 5 minutes.\n"
        f"If you did not request this, ignore this email."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


# In-memory OTP store
OTP_STORE: Dict[str, Dict[str, Any]] = {}  # email -> {code, expires, attempts}


@router.post("/start")
async def start(data: StudentStartRequest, request: Request):
    require_ip_allowlist(request)

    email = (data.email or "").strip().lower()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email")

    # Domain restriction (tamu.edu)
    if not domain_allowed(email):
        raise HTTPException(status_code=403, detail="Only TAMU emails are allowed")

    code = f"{random.randint(100000, 999999)}"
    expires = int(time.time()) + 300  # 5 minutes

    OTP_STORE[email] = {"code": code, "expires": expires, "attempts": 0}

    send_student_otp_email(email, code)
    return {"message": "OTP sent to email", "otp_expires_in": 300}


@router.post("/verify")
async def verify(data: StudentVerifyRequest, request: Request):
    require_ip_allowlist(request)

    email = (data.email or "").strip().lower()
    otp = (data.otp or "").strip()

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

    # Mint same-shaped response as admin: {token, user, expires_in}
    return mint_app_token(email=email, role="student")