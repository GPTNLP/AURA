# backend/hash_admin_users_cli.py
import json
import getpass
from pathlib import Path

from hash_passwords import hash_password

def main():
    path = Path(__file__).resolve().parent / "admin_users.json"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    admins = data.get("admins", [])
    if not admins:
        print("No admins found in admin_users.json under key 'admins'")
        return

    for admin in admins:
        email = admin.get("email", "<unknown>")
        pw = getpass.getpass(f"Enter password for {email}: ").strip()
        admin["password_hash"] = hash_password(pw)

        # Optional: if you still have plaintext fields, wipe them
        if "password" in admin:
            admin.pop("password", None)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("\n✅ Saved PBKDF2 password hashes to admin_users.json\n")

if __name__ == "__main__":
    main()