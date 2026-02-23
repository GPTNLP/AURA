import os
import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BACKEND_DIR / "storage" / "aura.sqlite"

DB_PATH = Path(os.getenv("AURA_SQLITE_PATH", str(DEFAULT_DB)))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c

def init_db() -> None:
    with _conn() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ta_users (
                email TEXT PRIMARY KEY,
                added_by TEXT,
                added_ts INTEGER
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_owners (
                path TEXT PRIMARY KEY,
                owner_email TEXT NOT NULL,
                owner_role TEXT NOT NULL,
                uploaded_ts INTEGER NOT NULL
            )
            """
        )

# ---------------------------
# TA users
# ---------------------------
def ta_is_enabled(email: str) -> bool:
    email = (email or "").strip().lower()
    if not email:
        return False
    with _conn() as con:
        row = con.execute("SELECT email FROM ta_users WHERE email = ?", (email,)).fetchone()
        return row is not None

def ta_list() -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute("SELECT email, added_by, added_ts FROM ta_users ORDER BY email").fetchall()
        return [dict(r) for r in rows]

def ta_add(email: str, added_by: str) -> None:
    email = (email or "").strip().lower()
    added_by = (added_by or "").strip().lower()
    if not email:
        raise ValueError("Missing email")
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO ta_users(email, added_by, added_ts) VALUES(?,?,?)",
            (email, added_by, int(time.time())),
        )

def ta_remove(email: str) -> None:
    email = (email or "").strip().lower()
    with _conn() as con:
        con.execute("DELETE FROM ta_users WHERE email = ?", (email,))

# ---------------------------
# Document ownership
# ---------------------------
def doc_set_owner(path: str, owner_email: str, owner_role: str) -> None:
    path = (path or "").replace("\\", "/").lstrip("/")
    owner_email = (owner_email or "").strip().lower()
    owner_role = (owner_role or "").strip().lower()
    if not path or not owner_email or not owner_role:
        raise ValueError("Invalid owner record")
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO doc_owners(path, owner_email, owner_role, uploaded_ts) VALUES(?,?,?,?)",
            (path, owner_email, owner_role, int(time.time())),
        )

def doc_get_owner(path: str) -> Optional[Dict[str, Any]]:
    path = (path or "").replace("\\", "/").lstrip("/")
    if not path:
        return None
    with _conn() as con:
        row = con.execute(
            "SELECT path, owner_email, owner_role, uploaded_ts FROM doc_owners WHERE path = ?",
            (path,),
        ).fetchone()
        return dict(row) if row else None

def doc_delete_owner(path: str) -> None:
    path = (path or "").replace("\\", "/").lstrip("/")
    with _conn() as con:
        con.execute("DELETE FROM doc_owners WHERE path = ?", (path,))

def doc_move_owner(src: str, dst: str) -> None:
    src = (src or "").replace("\\", "/").lstrip("/")
    dst = (dst or "").replace("\\", "/").lstrip("/")
    with _conn() as con:
        con.execute("UPDATE doc_owners SET path = ? WHERE path = ?", (dst, src))