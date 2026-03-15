# backend/security_tokens.py
import os
import time
import json
import base64
import hmac
import hashlib
from pathlib import Path
from typing import Dict, Any

AUTH_SECRET = os.getenv("AUTH_SECRET", "")
AUTH_TOKEN_TTL = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "3600"))  # default 1 hour


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _storage_dir() -> Path:
    p = Path(__file__).resolve().parent / "storage"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _revocations_path() -> Path:
    return _storage_dir() / "token_revocations.json"


def _read_revocations() -> Dict[str, int]:
    path = _revocations_path()
    if not path.exists():
      path.write_text("{}", encoding="utf-8")

    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        out: Dict[str, int] = {}
        for k, v in data.items():
            email = (k or "").strip().lower()
            if not email:
                continue
            try:
                out[email] = int(v)
            except Exception:
                continue
        return out
    except Exception:
        return {}


def _write_revocations(data: Dict[str, int]) -> None:
    path = _revocations_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def revoke_user_tokens(email: str) -> int:
    """
    Invalidate all existing tokens for this user by recording a cutoff timestamp.
    Any token with iat < cutoff is rejected.
    """
    email = (email or "").strip().lower()
    if not email:
        return 0

    now = int(time.time())
    data = _read_revocations()
    data[email] = now
    _write_revocations(data)
    return now


def get_user_revoked_after(email: str) -> int:
    email = (email or "").strip().lower()
    if not email:
        return 0
    data = _read_revocations()
    return int(data.get(email, 0) or 0)


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
    exp = int(payload.get("exp", 0) or 0)
    if exp and time.time() > exp:
        raise ValueError("Token expired")

    email = (payload.get("sub") or "").strip().lower()
    iat = int(payload.get("iat", 0) or 0)

    revoked_after = get_user_revoked_after(email)
    if revoked_after and iat < revoked_after:
        raise ValueError("Token revoked")

    return payload


def mint_app_token(email: str, role: str) -> Dict[str, Any]:
    now = int(time.time())
    email = (email or "").strip().lower()
    role = (role or "").strip().lower()

    payload = {
        "sub": email,
        "role": role,
        "iat": now,
        "exp": now + AUTH_TOKEN_TTL,
    }

    return {
        "token": sign_token(payload),
        "user": {"email": email, "role": role},
        "expires_in": AUTH_TOKEN_TTL,
    }