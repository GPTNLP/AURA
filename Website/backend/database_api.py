# database_api.py (FULL REPLACE)
import os
import json
import shutil
import time
import math
import re
from typing import List, Optional, Dict, Any, Tuple, Iterable

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pypdf import PdfReader

from security import require_auth, require_ip_allowlist
from aura_db import init_db, doc_set_owner, doc_get_owner, doc_delete_owner, doc_move_owner

router = APIRouter(tags=["database"])
init_db()

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------
# Optional: LightRAG (Jetson/local)
# ---------------------------
HAS_RAG = False
LightRAG = None
QueryParam = None
try:
    from lightrag_local import LightRAG as _LightRAG, QueryParam as _QueryParam

    LightRAG = _LightRAG
    QueryParam = _QueryParam
    HAS_RAG = True
except Exception:
    HAS_RAG = False

# ---------------------------
# Paths / env
# ---------------------------
DOCS_ABS = (os.getenv("AURA_DOCUMENTS_DIR", "") or "").strip()
DBS_ABS = (os.getenv("AURA_DATABASES_DIR", "") or "").strip()

DOCS_REL_OR_ABS = (os.getenv("AURA_DOCS_DIR", "storage/documents") or "").strip()
DB_REL_OR_ABS = (os.getenv("AURA_DB_DIR", "storage/databases") or "").strip()

if DOCS_ABS:
    DOCUMENTS_DIR = DOCS_ABS
else:
    DOCUMENTS_DIR = DOCS_REL_OR_ABS if os.path.isabs(DOCS_REL_OR_ABS) else os.path.join(BACKEND_DIR, DOCS_REL_OR_ABS)

if DBS_ABS:
    RAG_ROOT_DIR = DBS_ABS
else:
    RAG_ROOT_DIR = DB_REL_OR_ABS if os.path.isabs(DB_REL_OR_ABS) else os.path.join(BACKEND_DIR, DB_REL_OR_ABS)

os.makedirs(DOCUMENTS_DIR, exist_ok=True)
os.makedirs(RAG_ROOT_DIR, exist_ok=True)

DEFAULT_LLM = os.getenv("AURA_LLM_MODEL", "llama3.2:3b")
DEFAULT_EMBED = os.getenv("AURA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_URL = os.getenv("AURA_OLLAMA_URL", "http://127.0.0.1:11434")

DEFAULT_CHAT_MODE = os.getenv("AURA_CHAT_MODE", "vector")
DEFAULT_TOP_K = int(os.getenv("AURA_TOP_K", "4"))

AURA_ENABLE_RAG = os.getenv("AURA_ENABLE_RAG", "0").strip() == "1"
DEVICE_SHARED_SECRET = (os.getenv("DEVICE_SHARED_SECRET", "") or "").strip()

# ---------------------------
# Auth helpers
# ---------------------------
def _role(payload: Dict[str, Any]) -> str:
    return str(payload.get("role") or "").lower()

def _email(payload: Dict[str, Any]) -> str:
    return str(payload.get("sub") or "").strip().lower()

def require_any_user(request: Request) -> Dict[str, Any]:
    require_ip_allowlist(request)
    return require_auth(request)

def require_admin(request: Request) -> Dict[str, Any]:
    payload = require_any_user(request)
    if _role(payload) != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload

def require_admin_or_ta(request: Request) -> Dict[str, Any]:
    payload = require_any_user(request)
    if _role(payload) not in ("admin", "ta"):
        raise HTTPException(status_code=403, detail="Admin/TA only")
    return payload

def require_device_secret(x_device_secret: Optional[str]):
    expected = DEVICE_SHARED_SECRET
    got = (x_device_secret or "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="DEVICE_SHARED_SECRET is not configured on backend")
    if got != expected:
        raise HTTPException(status_code=403, detail="Invalid device secret")

def require_user_or_device(request: Request, x_device_secret: Optional[str] = None):
    if x_device_secret:
        require_device_secret(x_device_secret)
        return {"role": "device", "sub": "device"}
    return require_any_user(request)

# ---------------------------
# Safe path helpers
# ---------------------------
def _safe_join(root: str, rel: str) -> str:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    full = os.path.normpath(os.path.join(root, rel))
    root_norm = os.path.normpath(root)
    if not (full == root_norm or full.startswith(root_norm + os.sep)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return full

def _walk_tree(base: str, rel: str = "") -> Dict[str, Any]:
    cur = _safe_join(base, rel)
    name = os.path.basename(cur) if rel else "documents"
    node = {
        "name": name,
        "path": rel.replace("\\", "/"),
        "kind": "dir",
        "children": [],
    }

    try:
        entries = sorted(os.listdir(cur), key=lambda x: x.lower())
    except Exception:
        entries = []

    for entry in entries:
        entry_rel = f"{rel}/{entry}".strip("/")
        full = os.path.join(cur, entry)
        if os.path.isdir(full):
            node["children"].append(_walk_tree(base, entry_rel))
        else:
            node["children"].append(
                {
                    "name": entry,
                    "path": entry_rel.replace("\\", "/"),
                    "kind": "file",
                    "size": os.path.getsize(full) if os.path.exists(full) else 0,
                }
            )
    return node

# ---------------------------
# DB paths
# ---------------------------
def _db_dir(name: str) -> str:
    return _safe_join(RAG_ROOT_DIR, name)

def _db_config_path(name: str) -> str:
    return os.path.join(_db_dir(name), "db.json")

def _db_stats_path(name: str) -> str:
    return os.path.join(_db_dir(name), "stats.json")

def _db_workdir(name: str) -> str:
    return _db_dir(name)

def _db_manifest_path(name: str) -> str:
    return os.path.join(_db_dir(name), "source_manifest.json")

def _load_db_config(name: str) -> Dict[str, Any]:
    p = _db_config_path(name)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Database not found")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Invalid database config")

def _save_db_config(name: str, cfg: Dict[str, Any]):
    os.makedirs(_db_dir(name), exist_ok=True)
    with open(_db_config_path(name), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def _save_simple_stats(name: str, stats: Dict[str, Any]):
    os.makedirs(_db_dir(name), exist_ok=True)
    with open(_db_stats_path(name), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def _load_simple_stats(name: str) -> Dict[str, Any]:
    p = _db_stats_path(name)
    if not os.path.exists(p):
        return {"chunk_count": 0, "files_found": 0, "skipped_files": 0, "mode": "simple"}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"chunk_count": 0, "files_found": 0, "skipped_files": 0, "mode": "simple"}

# ---------------------------
# LightRAG cache
# ---------------------------
_RAG_CACHE: Dict[str, Tuple[Any, float]] = {}
_RAG_CACHE_TTL_S = float(os.getenv("AURA_RAG_CACHE_TTL_S", "3600"))

def _get_rag(db_name: str):
    if not (AURA_ENABLE_RAG and HAS_RAG):
        raise RuntimeError("RAG disabled")

    now = time.time()
    hit = _RAG_CACHE.get(db_name)
    if hit:
        rag, ts = hit
        if (now - ts) < _RAG_CACHE_TTL_S:
            return rag

    cfg = _load_db_config(db_name)
    rag = LightRAG(
        working_dir=_db_workdir(db_name),
        llm_model_name=str(cfg.get("llm_model") or DEFAULT_LLM),
        embed_model_name=str(cfg.get("embed_model") or DEFAULT_EMBED),
        ollama_base_url=str(cfg.get("ollama_url") or OLLAMA_URL),
    )
    _RAG_CACHE[db_name] = (rag, now)
    return rag

def _invalidate_rag(db_name: str):
    _RAG_CACHE.pop(db_name, None)

# ---------------------------
# Models
# ---------------------------
class MkdirRequest(BaseModel):
    path: str

class MoveRequest(BaseModel):
    src: str
    dst: str

class CreateDBRequest(BaseModel):
    name: str
    folders: List[str] = []

class BuildDBRequest(BaseModel):
    name: str
    folders: Optional[List[str]] = None
    force: bool = True

class ChatRequest(BaseModel):
    db: str
    query: str
    mode: Optional[str] = None
    top_k: Optional[int] = None

# ---------------------------
# Text / chunking helpers
# ---------------------------
def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

def _read_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        parts: List[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                pass
        return "\n".join(parts)
    except Exception:
        return ""

def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    chunks: List[str] = []
    i = 0
    n = len(text)

    while i < n:
        j = min(n, i + chunk_size)
        chunk = text[i:j].strip()
        if chunk:
            chunks.append(chunk)
        if j >= n:
            break
        i = max(i + 1, j - overlap)

    return chunks

# ---------------------------
# Manifest helpers
# ---------------------------
def _collect_db_source_files(folders: List[str]) -> List[str]:
    found: List[str] = []
    for folder in folders:
        base = _safe_join(DOCUMENTS_DIR, folder)
        if not os.path.exists(base) or not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for fn in sorted(files):
                ext = os.path.splitext(fn)[1].lower()
                if ext in [".pdf", ".txt", ".md"]:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, DOCUMENTS_DIR).replace("\\", "/")
                    found.append(rel)
    return sorted(found)

def _save_source_manifest(db_name: str, folders: List[str], files: List[str]):
    payload = {
        "db": db_name,
        "folders": folders,
        "files": files,
        "updated_ts": int(time.time()),
    }
    with open(_db_manifest_path(db_name), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def _load_source_manifest(db_name: str) -> Dict[str, Any]:
    p = _db_manifest_path(db_name)
    if not os.path.exists(p):
        cfg = _load_db_config(db_name)
        folders = list(cfg.get("folders") or [])
        files = _collect_db_source_files(folders)
        _save_source_manifest(db_name, folders, files)
    try:
        with open(_db_manifest_path(db_name), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        cfg = _load_db_config(db_name)
        folders = list(cfg.get("folders") or [])
        files = _collect_db_source_files(folders)
        payload = {"db": db_name, "folders": folders, "files": files, "updated_ts": int(time.time())}
        return payload

# ---------------------------
# Endpoints: Documents
# ---------------------------
@router.get("/api/documents/download")
def download_document(
    path: str,
    request: Request,
    x_device_secret: Optional[str] = Header(default=None, alias="X-Device-Secret"),
):
    require_user_or_device(request, x_device_secret)
    full_path = _safe_join(DOCUMENTS_DIR, path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)

@router.get("/api/documents/tree")
def documents_tree(request: Request):
    require_any_user(request)
    return {"root": "documents", "path": DOCUMENTS_DIR, "tree": _walk_tree(DOCUMENTS_DIR)}

@router.post("/api/documents/mkdir")
def documents_mkdir(req: MkdirRequest, request: Request):
    require_admin_or_ta(request)
    full = _safe_join(DOCUMENTS_DIR, req.path)
    os.makedirs(full, exist_ok=True)
    return {"ok": True, "created": req.path}

@router.post("/api/documents/upload")
async def documents_upload(request: Request, path: str = "", files: List[UploadFile] = File(...)):
    payload = require_admin_or_ta(request)
    dest_dir = _safe_join(DOCUMENTS_DIR, path)
    os.makedirs(dest_dir, exist_ok=True)

    saved = 0
    owner_email = _email(payload)
    owner_role = _role(payload)

    for f in files:
        name = os.path.basename(f.filename or "file")
        out = os.path.join(dest_dir, name)
        with open(out, "wb") as w:
            w.write(await f.read())
        saved += 1

        rel_source = os.path.relpath(out, DOCUMENTS_DIR).replace("\\", "/")
        doc_set_owner(rel_source, owner_email, owner_role)

    return {"ok": True, "saved": saved, "path": path}

@router.delete("/api/documents/delete")
def documents_delete(request: Request, path: str):
    rel_norm = (path or "").replace("\\", "/").lstrip("/")
    full = _safe_join(DOCUMENTS_DIR, path)
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="Path not found")

    payload = require_admin_or_ta(request)
    role = _role(payload)
    email = _email(payload)

    owner = doc_get_owner(rel_norm)

    if os.path.isfile(full):
        if role != "admin":
            if not owner or owner.get("owner_email") != email:
                raise HTTPException(status_code=403, detail="You can only delete your own uploaded files")
        try:
            os.remove(full)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Delete failed: {e}")
        doc_delete_owner(rel_norm)
        return {"ok": True, "deleted": rel_norm}

    if os.path.isdir(full):
        if role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can delete folders")
        try:
            shutil.rmtree(full)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Delete failed: {e}")
        return {"ok": True, "deleted": rel_norm}

    raise HTTPException(status_code=400, detail="Unsupported path type")

@router.post("/api/documents/move")
def documents_move(req: MoveRequest, request: Request):
    payload = require_admin_or_ta(request)

    src_rel = (req.src or "").replace("\\", "/").lstrip("/")
    dst_rel = (req.dst or "").replace("\\", "/").lstrip("/")

    if not src_rel or not dst_rel:
        raise HTTPException(status_code=400, detail="src and dst required")

    src = _safe_join(DOCUMENTS_DIR, src_rel)
    dst = _safe_join(DOCUMENTS_DIR, dst_rel)

    if not os.path.exists(src):
        raise HTTPException(status_code=404, detail="Source path not found")

    role = _role(payload)
    email = _email(payload)

    if os.path.isfile(src):
        owner = doc_get_owner(src_rel)
        if role != "admin":
            if not owner or owner.get("owner_email") != email:
                raise HTTPException(status_code=403, detail="You can only move your own uploaded files")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        doc_move_owner(src_rel, dst_rel)
        return {"ok": True, "src": src_rel, "dst": dst_rel}

    if os.path.isdir(src):
        if role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can move folders")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        return {"ok": True, "src": src_rel, "dst": dst_rel}

    raise HTTPException(status_code=400, detail="Unsupported path type")

# ---------------------------
# Endpoints: DBs
# ---------------------------
@router.get("/api/databases/list")
def list_databases(request: Request):
    require_any_user(request)
    out = []
    if os.path.exists(RAG_ROOT_DIR):
        for name in sorted(os.listdir(RAG_ROOT_DIR)):
            if os.path.exists(_db_config_path(name)):
                out.append(name)
    return {"databases": out}

@router.post("/api/databases/create")
def create_database(req: CreateDBRequest, request: Request):
    require_admin(request)

    db_dir = _db_dir(req.name)
    os.makedirs(db_dir, exist_ok=True)

    cfg = {
        "name": req.name,
        "folders": req.folders,
        "llm_model": DEFAULT_LLM,
        "embed_model": DEFAULT_EMBED,
        "ollama_url": OLLAMA_URL,
        "engine": "lightrag" if (AURA_ENABLE_RAG and HAS_RAG) else "simple",
    }
    _save_db_config(req.name, cfg)
    _save_source_manifest(req.name, req.folders, _collect_db_source_files(req.folders))
    _invalidate_rag(req.name)
    return {"ok": True, "db": req.name, "config": cfg}

@router.get("/api/databases/{db_name}/config")
def get_database_config(db_name: str, request: Request):
    require_any_user(request)
    return _load_db_config(db_name)

@router.get("/api/databases/{db_name}/stats")
def database_stats(db_name: str, request: Request):
    require_any_user(request)
    cfg = _load_db_config(db_name)

    if AURA_ENABLE_RAG and HAS_RAG:
        try:
            rag = _get_rag(db_name)
            return {"db": db_name, "config": cfg, "stats": rag.stats()}
        except Exception:
            pass

    simple_stats = _load_simple_stats(db_name)
    return {
        "db": db_name,
        "config": cfg,
        "stats": {
            "chunk_count": int(simple_stats.get("chunk_count") or 0),
            "vdb_path": _db_dir(db_name),
            "engine": "simple",
            "files_found": int(simple_stats.get("files_found") or 0),
            "skipped_files": int(simple_stats.get("skipped_files") or 0),
        },
    }

@router.post("/api/databases/build")
async def build_database(req: BuildDBRequest, request: Request):
    require_admin(request)

    cfg = _load_db_config(req.name)
    folders = req.folders if req.folders is not None else cfg.get("folders", [])

    if not folders:
        raise HTTPException(status_code=400, detail="No folders selected for this database")

    workdir = _db_workdir(req.name)
    os.makedirs(workdir, exist_ok=True)

    all_files: List[str] = []
    for folder in folders:
        base = _safe_join(DOCUMENTS_DIR, folder)
        if not os.path.exists(base) or not os.path.isdir(base):
            raise HTTPException(status_code=400, detail=f"Folder not found: {folder}")

        for root, _, files in os.walk(base):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in [".pdf", ".txt", ".md"]:
                    all_files.append(os.path.join(root, fn))

    if not all_files:
        raise HTTPException(status_code=400, detail="No indexable files (.pdf/.txt/.md) found")

    if AURA_ENABLE_RAG and HAS_RAG:
        try:
            rag = _get_rag(req.name)
            if req.force:
                rag.reset()

            inserted_chunks = 0
            skipped_files = 0

            for path in sorted(all_files):
                ext = os.path.splitext(path)[1].lower()
                text = _read_pdf(path) if ext == ".pdf" else _read_text(path)
                if not text.strip():
                    skipped_files += 1
                    continue

                rel_source = os.path.relpath(path, DOCUMENTS_DIR).replace("\\", "/")
                header = f"[SOURCE FILE: {rel_source}]\n\n"
                chunks = _chunk_text(header + text)

                for c in chunks:
                    await rag.ainsert(c, meta={"source": rel_source})
                    inserted_chunks += 1

            cfg["folders"] = folders
            cfg["engine"] = "lightrag"
            _save_db_config(req.name, cfg)
            _save_source_manifest(req.name, folders, _collect_db_source_files(folders))

            try:
                rag.flush()
            except Exception:
                pass

            _invalidate_rag(req.name)

            return {
                "ok": True,
                "status": "Database built",
                "db": req.name,
                "folders": folders,
                "files_found": len(all_files),
                "skipped_files": skipped_files,
                "inserted_chunks": inserted_chunks,
                "stats": rag.stats(),
                "engine": "lightrag",
            }
        except Exception as e:
            print(f"[database_api] LightRAG build failed, falling back to simple. Error: {e}")

    inserted_chunks = 0
    skipped_files = 0

    chunks_out: List[Dict[str, Any]] = []

    for path in sorted(all_files):
        ext = os.path.splitext(path)[1].lower()
        text = _read_pdf(path) if ext == ".pdf" else _read_text(path)
        if not text.strip():
            skipped_files += 1
            continue

        rel_source = os.path.relpath(path, DOCUMENTS_DIR).replace("\\", "/")
        header = f"[SOURCE FILE: {rel_source}]\n\n"
        chunks = _chunk_text(header + text)

        for c in chunks:
            chunks_out.append({"text": c, "meta": {"source": rel_source}})
            inserted_chunks += 1

    chunks_path = os.path.join(workdir, "chunks.jsonl")
    with open(chunks_path, "w", encoding="utf-8") as f:
        for row in chunks_out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats = {
        "chunk_count": inserted_chunks,
        "files_found": len(all_files),
        "skipped_files": skipped_files,
        "mode": "simple",
        "vdb_path": workdir,
        "updated_ts": int(time.time()),
    }
    _save_simple_stats(req.name, stats)

    cfg["folders"] = folders
    cfg["engine"] = "simple"
    _save_db_config(req.name, cfg)
    _save_source_manifest(req.name, folders, _collect_db_source_files(folders))

    return {
        "ok": True,
        "status": "Database built",
        "db": req.name,
        "folders": folders,
        "files_found": len(all_files),
        "skipped_files": skipped_files,
        "inserted_chunks": inserted_chunks,
        "stats": stats,
        "engine": "simple",
    }

@router.post("/api/databases/{db_name}/sync_up")
async def sync_db_up(
    db_name: str,
    x_device_secret: Optional[str] = Header(default=None, alias="X-Device-Secret"),
    files: List[UploadFile] = File(...),
):
    require_device_secret(x_device_secret)

    db_dir = _db_dir(db_name)
    os.makedirs(db_dir, exist_ok=True)

    saved = []
    allowed = {"faiss.index", "embeddings.npy", "meta.json", "db.json", "chunks.jsonl", "stats.json"}

    for f in files:
        if f.filename in allowed:
            out = os.path.join(db_dir, f.filename)
            with open(out, "wb") as w:
                w.write(await f.read())
            saved.append(f.filename)

    return {"ok": True, "saved": saved, "db": db_name}

@router.get("/api/databases/{db_name}/sync_down/{filename}")
def sync_db_down(
    db_name: str,
    filename: str,
    x_device_secret: Optional[str] = Header(default=None, alias="X-Device-Secret"),
):
    require_device_secret(x_device_secret)

    allowed = {"faiss.index", "embeddings.npy", "meta.json", "db.json", "chunks.jsonl", "stats.json"}
    if filename not in allowed:
        raise HTTPException(status_code=400, detail="Invalid vector file")

    full_path = os.path.join(_db_dir(db_name), filename)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Vector file not found")
    return FileResponse(full_path)

@router.get("/api/databases/{db_name}/source_manifest")
def get_source_manifest(
    db_name: str,
    request: Request,
    x_device_secret: Optional[str] = Header(default=None, alias="X-Device-Secret"),
):
    require_user_or_device(request, x_device_secret)
    cfg = _load_db_config(db_name)
    folders = list(cfg.get("folders") or [])
    files = _collect_db_source_files(folders)
    _save_source_manifest(db_name, folders, files)
    return {
        "ok": True,
        "db": db_name,
        "folders": folders,
        "files": files,
        "count": len(files),
        "updated_ts": int(time.time()),
    }

@router.post("/api/databases/{db_name}/set_folders")
def set_database_folders(db_name: str, req: CreateDBRequest, request: Request):
    require_admin(request)
    cfg = _load_db_config(db_name)
    cfg["folders"] = req.folders
    _save_db_config(db_name, cfg)
    _save_source_manifest(db_name, req.folders, _collect_db_source_files(req.folders))
    return {"ok": True, "db": db_name, "folders": req.folders}