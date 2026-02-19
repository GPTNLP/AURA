import os
import json
import base64
import hashlib
import hmac
import getpass

def hash_password(password: str, iterations: int = 200_000) -> str:
    """
    Returns string format:
    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
    """
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("utf-8").rstrip("="),
        base64.urlsafe_b64encode(dk).decode("utf-8").rstrip("="),
    )

path = "admin_users.json"
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

for admin in data["admins"]:
    email = admin["email"]
    pw = getpass.getpass(f"Enter password for {email}: ").strip()
    admin["password_hash"] = hash_password(pw)

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("\n✅ Saved PBKDF2 password hashes to admin_users.json\n")
