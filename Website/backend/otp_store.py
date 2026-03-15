# backend/otp_store.py
import os
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any


def hash_code(code: str) -> str:
    return hashlib.sha256((code or "").strip().encode("utf-8")).hexdigest()


class OTPStore:
    """
    File-backed OTP store keyed by:
        prefix + normalized email

    This prevents:
    - one user's OTP overwriting another user's OTP
    - admin OTPs colliding with TA/student OTPs
    """

    def __init__(self, prefix: str = "otp"):
        self.prefix = (prefix or "otp").strip().lower()
        base_dir = Path(__file__).resolve().parent / "storage"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.path = base_dir / f"{self.prefix}_store.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _read(self) -> Dict[str, Any]:
        self._ensure_file()
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write(self, data: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _key(self, email: str) -> str:
        return (email or "").strip().lower()

    def set(self, email: str, code: str, ttl_seconds: int = 300) -> None:
        email_key = self._key(email)
        if not email_key:
            return

        now = int(time.time())
        expires = now + int(ttl_seconds)

        data = self._read()
        data[email_key] = {
            "email": email_key,
            "otp_hash": hash_code(code),
            "attempts": 0,
            "created": now,
            "expires": expires,
        }
        self._write(data)

    def get(self, email: str) -> Optional[Dict[str, Any]]:
        email_key = self._key(email)
        if not email_key:
            return None

        data = self._read()
        rec = data.get(email_key)

        if not isinstance(rec, dict):
            return None

        expires = int(rec.get("expires", 0) or 0)
        if expires and time.time() > expires:
            data.pop(email_key, None)
            self._write(data)
            return None

        return rec

    def incr_attempts(self, email: str) -> int:
        email_key = self._key(email)
        if not email_key:
            return 0

        data = self._read()
        rec = data.get(email_key)
        if not isinstance(rec, dict):
            return 0

        rec["attempts"] = int(rec.get("attempts", 0)) + 1
        data[email_key] = rec
        self._write(data)
        return int(rec["attempts"])

    def delete(self, email: str) -> None:
        email_key = self._key(email)
        if not email_key:
            return

        data = self._read()
        if email_key in data:
            data.pop(email_key, None)
            self._write(data)

    def clear_expired(self) -> None:
        now = int(time.time())
        data = self._read()

        cleaned: Dict[str, Any] = {}
        for key, rec in data.items():
            if not isinstance(rec, dict):
                continue
            expires = int(rec.get("expires", 0) or 0)
            if expires and now > expires:
                continue
            cleaned[key] = rec

        self._write(cleaned)