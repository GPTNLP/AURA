# backend/otp_store.py
import os
import time
import hashlib
import hmac
from typing import Any, Dict, Optional

try:
    import redis  # type: ignore
except Exception:
    redis = None

# In-memory fallback (dev only)
_MEM: Dict[str, Dict[str, Any]] = {}

def _now() -> int:
    return int(time.time())

def _pepper() -> bytes:
    # IMPORTANT: set OTP_PEPPER in Azure
    return (os.getenv("OTP_PEPPER", "") or "dev-pepper").encode("utf-8")

def hash_code(code: str) -> str:
    # Hash OTP so we never store plaintext
    return hmac.new(_pepper(), code.encode("utf-8"), hashlib.sha256).hexdigest()

def _redis_client():
    """
    Supports:
      - REDIS_URL (recommended) e.g. rediss://:<password>@host:6380/0
      - or REDIS_HOST/REDIS_PORT/REDIS_PASSWORD
    """
    url = os.getenv("REDIS_URL", "").strip()
    if url and redis:
        return redis.Redis.from_url(url, decode_responses=True)

    host = os.getenv("REDIS_HOST", "").strip()
    if host and redis:
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD", "").strip() or None
        use_tls = os.getenv("REDIS_TLS", "0").strip() in ("1", "true", "True")
        return redis.Redis(
            host=host,
            port=port,
            password=password,
            ssl=use_tls,
            decode_responses=True,
        )

    return None

class OTPStore:
    """
    Stores: email -> { otp_hash, expires, attempts }
    TTL enforced by Redis key expiry (or by checking expires in memory).
    """

    def __init__(self, prefix: str = "otp"):
        self.prefix = prefix
        self.r = _redis_client()

    def _key(self, email: str) -> str:
        return f"{self.prefix}:{email.lower().strip()}"

    def set(self, email: str, code: str, ttl_seconds: int) -> None:
        email = email.lower().strip()
        rec = {
            "otp_hash": hash_code(code),
            "expires": _now() + ttl_seconds,
            "attempts": 0,
        }

        if self.r:
            key = self._key(email)
            # store as hash fields
            self.r.hset(key, mapping={k: str(v) for k, v in rec.items()})
            self.r.expire(key, ttl_seconds)
        else:
            _MEM[email] = rec

    def get(self, email: str) -> Optional[Dict[str, Any]]:
        email = email.lower().strip()
        if self.r:
            key = self._key(email)
            data = self.r.hgetall(key)
            if not data:
                return None
            # normalize types
            return {
                "otp_hash": data.get("otp_hash", ""),
                "expires": int(data.get("expires", "0") or 0),
                "attempts": int(data.get("attempts", "0") or 0),
            }

        rec = _MEM.get(email)
        if not rec:
            return None
        # expire check
        if _now() > int(rec.get("expires", 0)):
            _MEM.pop(email, None)
            return None
        return rec

    def incr_attempts(self, email: str) -> int:
        email = email.lower().strip()
        if self.r:
            key = self._key(email)
            # Redis HINCRBY
            return int(self.r.hincrby(key, "attempts", 1))
        rec = self.get(email)
        if not rec:
            return 0
        rec["attempts"] = int(rec.get("attempts", 0)) + 1
        _MEM[email] = rec
        return rec["attempts"]

    def delete(self, email: str) -> None:
        email = email.lower().strip()
        if self.r:
            self.r.delete(self._key(email))
        else:
            _MEM.pop(email, None)