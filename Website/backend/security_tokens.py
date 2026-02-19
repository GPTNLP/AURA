import os
import time
import json
import base64
import hmac
import hashlib
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

AUTH_SECRET = os.getenv("AUTH_SECRET", "")
AUTH_TOKEN_TTL = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))


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
        raise RuntimeError("AUTH_SECRET missing")

    raw_b64, sig_b64 = token.split(".", 1)
    raw = _b64url_decode(raw_b64)
    sig = _b64url_decode(sig_b64)

    expected = hmac.new(AUTH_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid token signature")

    payload = json.loads(raw.decode("utf-8"))
    exp = int(payload.get("exp", 0))
    if exp and time.time() > exp:
        raise ValueError("Token expired")

    return payload


def mint_app_token(email: str, role: str) -> Dict[str, Any]:
    now = int(time.time())
    payload = {"sub": email, "role": role, "iat": now, "exp": now + AUTH_TOKEN_TTL}
    return {
        "token": sign_token(payload),
        "user": {"email": email, "role": role},
        "expires_in": AUTH_TOKEN_TTL,
    }
