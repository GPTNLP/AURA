# backend/hash_passwords.py
import os
import base64
import hashlib
import hmac

ALGO_PREFIX = "pbkdf2_sha256"

def _b64encode_nopad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def _b64decode_nopad(s: str) -> bytes:
    # add padding back
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))

def hash_password(password: str, iterations: int = 200_000) -> str:
    """
    Returns:
    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGO_PREFIX}${iterations}${_b64encode_nopad(salt)}${_b64encode_nopad(dk)}"

def verify_password(password: str, stored: str) -> bool:
    """
    Verifies a plaintext password against stored PBKDF2 hash.
    Uses constant-time compare.
    """
    try:
        if not isinstance(password, str) or not password:
            return False
        if not isinstance(stored, str) or not stored:
            return False

        parts = stored.split("$")
        if len(parts) != 4:
            return False

        algo, iter_s, salt_b64, hash_b64 = parts
        if algo != ALGO_PREFIX:
            return False

        iterations = int(iter_s)
        salt = _b64decode_nopad(salt_b64)
        expected = _b64decode_nopad(hash_b64)

        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False