# backend/admin_tools_api.py
import os
import shutil
import zipfile
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, UploadFile, File, HTTPException, Request

from security import require_auth
from database_bridge import InitializeDatabase

router = APIRouter(prefix="/admin-tools", tags=["admin-tools"])

# -------------------------
# Config (env overrides)
# -------------------------
BASE_DIR = Path(__file__).resolve().parent  # .../Website/backend
DOCS_STAGING_DIR = Path(os.getenv("DOCS_STAGING_DIR", str(BASE_DIR / "source_documents")))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(STORAGE_DIR / "chroma")))

# Jetson / Edge base URL (health + sync endpoint)
# Example: http://192.168.1.100:8000  OR your Tailscale IP like http://100.x.y.z:8000
NANO_BASE_URL = os.getenv("NANO_BASE_URL", "http://192.168.1.100:8000").rstrip("/")

# Embedding model name used in your database_bridge
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


# -------------------------
# Auth helper (admin only)
# -------------------------
def require_admin(request: Request):
    payload = require_auth(request)
    role = (payload or {}).get("role")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


@router.get("/health")
def admin_tools_health():
    return {
        "ok": True,
        "docs_staging_dir": str(DOCS_STAGING_DIR),
        "storage_dir": str(STORAGE_DIR),
        "chroma_dir": str(CHROMA_DIR),
        "nano_base_url": NANO_BASE_URL,
        "embed_model": EMBED_MODEL,
    }


@router.post("/api/upload")
async def upload_docs(request: Request, files: list[UploadFile] = File(...)):
    require_admin(request)

    # reset staging folder
    if DOCS_STAGING_DIR.exists():
        shutil.rmtree(DOCS_STAGING_DIR, ignore_errors=True)
    DOCS_STAGING_DIR.mkdir(parents=True, exist_ok=True)

    saved = 0
    for f in files:
        # basic safety: avoid weird paths
        name = Path(f.filename or "file").name
        out_path = DOCS_STAGING_DIR / name
        with open(out_path, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)
        saved += 1

    return {"status": f"Uploaded {saved} file(s)", "saved": saved}


@router.post("/api/build")
async def build_db(request: Request):
    require_admin(request)

    if not DOCS_STAGING_DIR.exists():
        raise HTTPException(status_code=400, detail="No staged documents folder found. Upload first.")

    try:
        # force_reload=True ensures a rebuild
        InitializeDatabase(EMBED_MODEL, str(DOCS_STAGING_DIR), force_reload=True)
        return {"status": "Database built successfully", "chroma_dir": str(CHROMA_DIR)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build failed: {e}")


@router.post("/api/deploy")
async def deploy_to_nano(request: Request):
    require_admin(request)

    if not CHROMA_DIR.exists():
        raise HTTPException(status_code=400, detail=f"No database found at {CHROMA_DIR}. Build first.")

    zip_path = BASE_DIR / "chroma_deploy.zip"

    # Create zip from CHROMA_DIR
    if zip_path.exists():
        zip_path.unlink(missing_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in CHROMA_DIR.rglob("*"):
                if p.is_file():
                    zf.write(p, arcname=str(p.relative_to(CHROMA_DIR)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Zip failed: {e}")

    # Send zip to Nano endpoint
    # Nano must implement: POST {NANO_BASE_URL}/api/sync-db (files={"file": ...})
    try:
        with open(zip_path, "rb") as f:
            resp = requests.post(
                f"{NANO_BASE_URL}/api/sync-db",
                files={"file": f},
                timeout=600,
            )
        # If Nano returns non-JSON, still show status
        try:
            body = resp.json()
        except Exception:
            body = {"text": resp.text[:2000]}

        if not resp.ok:
            raise HTTPException(
                status_code=502,
                detail=f"Nano error ({resp.status_code}): {body}",
            )

        return {"status": "Deploy successful", "nano_response": body}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to contact Nano at {NANO_BASE_URL}: {e}")


@router.get("/api/nano-status")
async def check_nano(request: Request):
    require_admin(request)

    try:
        resp = requests.get(f"{NANO_BASE_URL}/health", timeout=2)
        if resp.ok:
            try:
                data = resp.json()
            except Exception:
                data = {"text": resp.text[:2000]}
            return {"online": True, "details": data}
        return {"online": False, "details": {"status_code": resp.status_code}}
    except Exception:
        return {"online": False}