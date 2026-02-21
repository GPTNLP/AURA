# Website/backend/files_api.py
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from dotenv import load_dotenv

from security_tokens import verify_token

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

router = APIRouter(prefix="/files", tags=["files"])

KB_DIR = os.getenv("KB_DIR", str(Path(__file__).resolve().parents[1] / "ECEN_214_Docs"))
EDGE_ONLINE = os.getenv("EDGE_ONLINE", "0") == "1"


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


@router.get("/edge-status")
def edge_status(request: Request):
    require_student_or_admin(request)
    return {"online": bool(EDGE_ONLINE)}


@router.get("/list")
def list_files(request: Request, path: str = ""):
    require_student_or_admin(request)

    base = Path(KB_DIR)
    base.mkdir(parents=True, exist_ok=True)

    target = _safe_resolve(base, path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a folder")

    items: List[Dict[str, Any]] = []
    for entry in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        st = entry.stat()
        items.append(
            {
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size": st.st_size,
                "modified": int(st.st_mtime),
                "relative_path": str(entry.relative_to(base)).replace("\\", "/"),
            }
        )

    return {
        "root": str(base.resolve()).replace("\\", "/"),
        "path": str(target.relative_to(base)).replace("\\", "/"),
        "items": items,
    }


@router.post("/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    path: str = "",
):
    require_student_or_admin(request)

    base = Path(KB_DIR)
    base.mkdir(parents=True, exist_ok=True)

    target_dir = _safe_resolve(base, path)
    target_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for f in files:
        if not _allowed_filename(f.filename):
            raise HTTPException(status_code=400, detail=f"Bad filename: {f.filename}")

        out_path = _safe_resolve(target_dir, f.filename)
        data = await f.read()
        out_path.write_bytes(data)
        saved.append(
            {
                "name": f.filename,
                "bytes": len(data),
                "relative_path": str(out_path.relative_to(base)).replace("\\", "/"),
            }
        )

    return {"ok": True, "saved": saved}


@router.delete("/delete")
def delete_file_or_folder(request: Request, rel_path: str):
    require_admin(request)

    base = Path(KB_DIR)
    base.mkdir(parents=True, exist_ok=True)

    target = _safe_resolve(base, rel_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Not found")

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return {"ok": True, "deleted": rel_path}


@router.post("/mkdir")
def make_folder(request: Request, rel_path: str):
    require_admin(request)

    base = Path(KB_DIR)
    base.mkdir(parents=True, exist_ok=True)

    target = _safe_resolve(base, rel_path)
    target.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "created": rel_path}


@router.post("/build")
def build_vector_db(request: Request, force_rebuild: int = 0):
    require_student_or_admin(request)

    # Import heavy ML deps only when this endpoint is called
    try:
        from database_bridge import InitializeDatabase
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Build deps not installed or failed to import database_bridge: {e}",
        )

    docs_path = KB_DIR
    try:
        rag = InitializeDatabase(docs_path=docs_path, force_rebuild=bool(force_rebuild))
        if rag is None:
            raise HTTPException(status_code=400, detail="No docs found to build index (PDF/TXT).")
        return {"ok": True, "built": True, "docs_path": docs_path, "force_rebuild": bool(force_rebuild)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build failed: {e}")


@router.post("/deploy")
def deploy_to_edge(request: Request):
    require_student_or_admin(request)
    if not EDGE_ONLINE:
        raise HTTPException(status_code=409, detail="Edge device offline")
    return {
        "ok": False,
        "detail": "Deploy not wired yet. Tell me how you deploy to the Jetson (ssh/scp/rsync/docker).",
    }