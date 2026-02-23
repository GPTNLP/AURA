# backend/ta_auth_api.py
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

from security import require_ip_allowlist, domain_allowed
from security_tokens import mint_app_token
from otp_store import OTPStore, hash_code
from ta_store import is_ta

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

TA_OTP_TTL_SECONDS = int(os.getenv("TA_OTP_TTL_SECONDS", "300"))  # 5 min
TA_MAX_OTP_ATTEMPTS = int(os.getenv("TA_MAX_OTP_ATTEMPTS", "6"))

COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "aura_token")
COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "lax")
COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN", "")

router = APIRouter(prefix="/auth/ta", tags=["ta-auth"])
otp_store = OTPStore(prefix="taotp")

class TaStartReq(BaseModel):
    email: str

class TaVerifyReq(BaseModel):
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
    msg["Subject"] = "AURA TA Login Code"
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(
        f"Your AURA TA login code is: {code}\n\n"
        f"This code expires in {max(1, TA_OTP_TTL_SECONDS//60)} minutes.\n"
        f"If you did not request this, ignore this email."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

@router.post("/start")
async def start(data: TaStartReq, request: Request):
    require_ip_allowlist(request)

    email = (data.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Enter your TAMU email")

    if not domain_allowed(email):
        raise HTTPException(status_code=403, detail="Only @tamu.edu emails are allowed")

    # ✅ MUST be approved as TA before even receiving OTP
    if not is_ta(email):
        raise HTTPException(status_code=403, detail="Not approved as a TA. Contact admin.")

    code = f"{random.randint(100000, 999999)}"
    otp_store.set(email=email, code=code, ttl_seconds=TA_OTP_TTL_SECONDS)
    _send_otp_email(email, code)

    return {"message": "OTP sent", "otp_expires_in": TA_OTP_TTL_SECONDS}

@router.post("/verify")
async def verify(data: TaVerifyReq, request: Request, response: Response):
    require_ip_allowlist(request)

    email = (data.email or "").strip().lower()
    otp = (data.otp or "").strip()

    if not domain_allowed(email):
        raise HTTPException(status_code=403, detail="Only @tamu.edu emails are allowed")

    # ✅ MUST be approved as TA
    if not is_ta(email):
        raise HTTPException(status_code=403, detail="Not approved as a TA. Contact admin.")

    rec = otp_store.get(email)
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid code")

    if int(rec.get("expires", 0)) and time.time() > int(rec["expires"]):
        otp_store.delete(email)
        raise HTTPException(status_code=401, detail="Invalid code")

    attempts = otp_store.incr_attempts(email)
    if attempts > TA_MAX_OTP_ATTEMPTS:
        otp_store.delete(email)
        raise HTTPException(status_code=429, detail="Too many attempts")

    if hash_code(otp) != rec.get("otp_hash"):
        raise HTTPException(status_code=401, detail="Invalid code")

    otp_store.delete(email)

    result = mint_app_token(email=email, role="ta")
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