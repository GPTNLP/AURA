# Website/backend/files_api.py
import os
import io
import shutil
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from dotenv import load_dotenv

from security_tokens import verify_token

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

router = APIRouter(prefix="/files", tags=["files"])

# Where uploaded docs live (staging)
KB_DIR = Path(os.getenv("KB_DIR", str(Path(__file__).resolve().parents[1] / "storage" / "source_documents"))).resolve()

# Where vector DB output lives (chroma)
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(Path(__file__).resolve().parents[1] / "storage" / "chroma"))).resolve()

# Edge / Jetson target (optional in local dev)
# Example: http://192.168.1.100:8000  OR a Tailscale IP + port
NANO_BASE_URL = (os.getenv("NANO_BASE_URL", "") or "").strip().rstrip("/")

# Endpoint on the Nano that accepts the zip file
# Your teammate used: POST {NANO_BASE_URL}/api/sync-db
NANO_SYNC_ENDPOINT = (os.getenv("NANO_SYNC_ENDPOINT", "/api/sync-db") or "/api/sync-db").strip()
if not NANO_SYNC_ENDPOINT.startswith("/"):
    NANO_SYNC_ENDPOINT = "/" + NANO_SYNC_ENDPOINT

# Nano health endpoint (to detect online/offline)
NANO_HEALTH_ENDPOINT = (os.getenv("NANO_HEALTH_ENDPOINT", "/health") or "/health").strip()
if not NANO_HEALTH_ENDPOINT.startswith("/"):
    NANO_HEALTH_ENDPOINT = "/" + NANO_HEALTH_ENDPOINT


def _get_bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return auth.split(" ", 1)[1].strip()


def require_auth(request: Request) -> Dict[str, Any]:
    token = _get_bearer(request)
    try:
        return verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_student_or_admin(request: Request) -> Dict[str, Any]:
    payload = require_auth(request)
    role = payload.get("role")
    if role not in ("student", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return payload


def require_admin(request: Request) -> Dict[str, Any]:
    payload = require_auth(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload


def _safe_resolve(base: Path, rel: str) -> Path:
    rel = (rel or "").lstrip("/\\")
    p = (base / rel).resolve()
    if not str(p).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return p


def _allowed_filename(name: str) -> bool:
    bad = ["..", "/", "\\", "\x00"]
    return bool(name) and not any(x in name for x in bad)


def _nano_online() -> bool:
    if not NANO_BASE_URL:
        return False
    try:
        r = requests.get(f"{NANO_BASE_URL}{NANO_HEALTH_ENDPOINT}", timeout=2)
        return r.ok
    except Exception:
        return False


def _zip_dir_to_bytes(directory: Path) -> bytes:
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"Missing directory: {directory}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in directory.rglob("*"):
            if p.is_file():
                arcname = str(p.relative_to(directory)).replace("\\", "/")
                zf.write(p, arcname=arcname)
    return buf.getvalue()


@router.get("/edge-status")
def edge_status(request: Request):
    # You currently allow student or admin; keep it
    require_student_or_admin(request)
    return {"online": _nano_online()}


@router.post("/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
):
    # You can keep student upload if you want. If you want ADMIN ONLY later, change to require_admin(request)
    require_student_or_admin(request)

    KB_DIR.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in files:
        if not _allowed_filename(f.filename):
            raise HTTPException(status_code=400, detail=f"Bad filename: {f.filename}")

        out_path = _safe_resolve(KB_DIR, f.filename)
        data = await f.read()
        out_path.write_bytes(data)
        saved.append({"name": f.filename, "bytes": len(data), "path": str(out_path)})

    return {"ok": True, "saved": saved, "kb_dir": str(KB_DIR)}


@router.post("/build")
def build_vector_db(request: Request, force_rebuild: int = 0):
    # You can keep student build if you want. If you want ADMIN ONLY later, change to require_admin(request)
    require_student_or_admin(request)

    # Import heavy deps only here
    try:
        from database_bridge import InitializeDatabase
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import database_bridge: {e}")

    KB_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.parent.mkdir(parents=True, exist_ok=True)

    # Try to support BOTH signatures:
    # 1) InitializeDatabase("nomic-embed-text", DOCS_DIR, force_reload=True)
    # 2) InitializeDatabase(docs_path=..., force_rebuild=...)
    try:
        try:
            InitializeDatabase("nomic-embed-text", str(KB_DIR), force_reload=bool(force_rebuild))
        except TypeError:
            # fallback signature
            InitializeDatabase(docs_path=str(KB_DIR), force_rebuild=bool(force_rebuild))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build failed: {e}")

    return {
        "ok": True,
        "built": True,
        "docs_dir": str(KB_DIR),
        "chroma_dir": str(CHROMA_DIR),
        "force_rebuild": bool(force_rebuild),
    }


@router.post("/deploy")
def deploy_to_edge(request: Request):
    # Deploy should be admin-only.
    require_admin(request)

    if not NANO_BASE_URL:
        raise HTTPException(status_code=400, detail="NANO_BASE_URL is not set on the backend")

    if not _nano_online():
        raise HTTPException(status_code=409, detail="Edge device offline")

    if not CHROMA_DIR.exists():
        raise HTTPException(status_code=400, detail=f"No database to deploy. Missing {CHROMA_DIR}")

    # Zip chroma and push to Nano
    zip_bytes = _zip_dir_to_bytes(CHROMA_DIR)

    try:
        files = {"file": ("chroma.zip", zip_bytes, "application/zip")}
        r = requests.post(f"{NANO_BASE_URL}{NANO_SYNC_ENDPOINT}", files=files, timeout=600)
        if not r.ok:
            raise HTTPException(status_code=502, detail=f"Nano rejected deploy: {r.status_code} {r.text}")
        # Nano may return json; if not, return text
        try:
            return {"ok": True, "nano": r.json()}
        except Exception:
            return {"ok": True, "nano_text": r.text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to contact Nano at {NANO_BASE_URL}: {e}")