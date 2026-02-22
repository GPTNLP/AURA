# backend/database_api.py
import os
import json
import shutil
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader

from lightrag_local import LightRAG, QueryParam

router = APIRouter(tags=["database"])

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# -------------------------
# Storage layout (env overridable)
# -------------------------
DEFAULT_STORAGE_DIR = os.path.join(BACKEND_DIR, "storage")

STORAGE_DIR = os.path.abspath(
    os.getenv("AURA_STORAGE_DIR", DEFAULT_STORAGE_DIR)
    if os.path.isabs(os.getenv("AURA_STORAGE_DIR", "")) else
    os.path.join(BACKEND_DIR, os.getenv("AURA_STORAGE_DIR", "storage"))
)

DOCUMENTS_DIR = os.path.abspath(
    os.getenv("AURA_DOCUMENTS_DIR", os.path.join(STORAGE_DIR, "documents"))
    if os.path.isabs(os.getenv("AURA_DOCUMENTS_DIR", "")) else
    os.path.join(BACKEND_DIR, os.getenv("AURA_DOCUMENTS_DIR", os.path.join("storage", "documents")))
)

RAG_ROOT_DIR = os.path.abspath(
    os.getenv("AURA_DATABASES_DIR", os.path.join(STORAGE_DIR, "databases"))
    if os.path.isabs(os.getenv("AURA_DATABASES_DIR", "")) else
    os.path.join(BACKEND_DIR, os.getenv("AURA_DATABASES_DIR", os.path.join("storage", "databases")))
)

DEFAULT_LLM = os.getenv("AURA_LLM_MODEL", "llama3.2:3b")
DEFAULT_EMBED = os.getenv("AURA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_URL = os.getenv("AURA_OLLAMA_URL", "http://127.0.0.1:11434")

os.makedirs(DOCUMENTS_DIR, exist_ok=True)
os.makedirs(RAG_ROOT_DIR, exist_ok=True)


def _safe_join(root: str, rel: str) -> str:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    full = os.path.abspath(os.path.join(root, rel))
    root_abs = os.path.abspath(root)
    if not full.startswith(root_abs):
        raise HTTPException(status_code=400, detail="Invalid path")
    return full


def _db_dir(db_name: str) -> str:
    if not db_name or any(c in db_name for c in r'\/:*?"<>|'):
        raise HTTPException(status_code=400, detail="Invalid database name")
    return os.path.join(RAG_ROOT_DIR, db_name)


def _db_config_path(db_name: str) -> str:
    return os.path.join(_db_dir(db_name), "db.json")


def _db_workdir(db_name: str) -> str:
    # workdir == db folder (stores meta.json + embeddings.npy)
    return _db_dir(db_name)


def _load_db_config(db_name: str) -> Dict[str, Any]:
    p = _db_config_path(db_name)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Database not found")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_db_config(db_name: str, cfg: Dict[str, Any]):
    os.makedirs(_db_dir(db_name), exist_ok=True)
    with open(_db_config_path(db_name), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def _read_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        parts = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            if txt.strip():
                parts.append(txt)
        return "\n\n".join(parts)
    except Exception:
        return ""


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _chunk_text(text: str, max_chars: int = 2400, overlap: int = 250) -> List[str]:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + max_chars)
        chunk = text[i:j].strip()
        if chunk:
            chunks.append(chunk)
        if j >= n:
            break
        i = max(0, j - overlap)
    return chunks


def _walk_tree(root: str) -> Dict[str, Any]:
    def build(node_path: str) -> Dict[str, Any]:
        name = os.path.basename(node_path) or "documents"
        if os.path.isdir(node_path):
            children = []
            for item in sorted(os.listdir(node_path)):
                children.append(build(os.path.join(node_path, item)))
            return {"name": name, "type": "dir", "children": children}
        return {"name": name, "type": "file"}

    return build(root)


# -------------------------
# Models
# -------------------------
class MkdirRequest(BaseModel):
    path: str  # relative to DOCUMENTS_DIR


class MoveRequest(BaseModel):
    src: str   # relative to DOCUMENTS_DIR
    dst: str   # relative to DOCUMENTS_DIR


class CreateDBRequest(BaseModel):
    name: str
    folders: List[str] = []  # relative to DOCUMENTS_DIR


class BuildDBRequest(BaseModel):
    name: str
    folders: Optional[List[str]] = None
    force: bool = True


class ChatRequest(BaseModel):
    db: str
    query: str


# -------------------------
# Documents endpoints
# -------------------------
@router.get("/api/documents/tree")
def documents_tree():
    return {
        "root": "documents",
        "path": DOCUMENTS_DIR,
        "tree": _walk_tree(DOCUMENTS_DIR),
    }


@router.post("/api/documents/mkdir")
def documents_mkdir(req: MkdirRequest):
    full = _safe_join(DOCUMENTS_DIR, req.path)
    os.makedirs(full, exist_ok=True)
    return {"ok": True, "created": req.path}


@router.post("/api/documents/upload")
async def documents_upload(path: str = "", files: List[UploadFile] = File(...)):
    dest_dir = _safe_join(DOCUMENTS_DIR, path)
    os.makedirs(dest_dir, exist_ok=True)

    saved = 0
    for f in files:
        name = os.path.basename(f.filename or "file")
        out = os.path.join(dest_dir, name)
        with open(out, "wb") as w:
            w.write(await f.read())
        saved += 1

    return {"ok": True, "saved": saved, "path": path}


@router.delete("/api/documents/delete")
def documents_delete(path: str):
    full = _safe_join(DOCUMENTS_DIR, path)
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="Not found")
    if os.path.isdir(full):
        shutil.rmtree(full)
    else:
        os.remove(full)
    return {"ok": True, "deleted": path}


@router.post("/api/documents/move")
def documents_move(req: MoveRequest):
    src = _safe_join(DOCUMENTS_DIR, req.src)
    dst = _safe_join(DOCUMENTS_DIR, req.dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    return {"ok": True, "src": req.src, "dst": req.dst}


# -------------------------
# Databases endpoints
# -------------------------
@router.get("/api/databases")
def list_databases():
    out = []
    for name in sorted(os.listdir(RAG_ROOT_DIR)):
        p = os.path.join(RAG_ROOT_DIR, name)
        if not os.path.isdir(p):
            continue
        if os.path.exists(_db_config_path(name)):
            out.append(name)
    return {"databases": out}


@router.post("/api/databases/create")
def create_database(req: CreateDBRequest):
    db_dir = _db_dir(req.name)
    os.makedirs(db_dir, exist_ok=True)

    cfg = {
        "name": req.name,
        "folders": req.folders,
        "llm_model": DEFAULT_LLM,
        "embed_model": DEFAULT_EMBED,
        "ollama_url": OLLAMA_URL,
    }
    _save_db_config(req.name, cfg)
    return {"ok": True, "db": req.name, "config": cfg}


@router.get("/api/databases/{db_name}/config")
def get_database_config(db_name: str):
    return _load_db_config(db_name)


@router.get("/api/databases/{db_name}/stats")
def database_stats(db_name: str):
    cfg = _load_db_config(db_name)
    rag = LightRAG(
        working_dir=_db_workdir(db_name),
        llm_model_name=str(cfg.get("llm_model") or DEFAULT_LLM),
        embed_model_name=str(cfg.get("embed_model") or DEFAULT_EMBED),
        ollama_base_url=str(cfg.get("ollama_url") or OLLAMA_URL),
    )
    return {"db": db_name, "config": cfg, "stats": rag.stats()}


@router.post("/api/databases/build")
async def build_database(req: BuildDBRequest):
    cfg = _load_db_config(req.name)
    folders = req.folders if req.folders is not None else cfg.get("folders", [])

    if not folders:
        raise HTTPException(status_code=400, detail="No folders selected for this database")

    workdir = _db_workdir(req.name)
    os.makedirs(workdir, exist_ok=True)

    rag = LightRAG(
        working_dir=workdir,
        llm_model_name=str(cfg.get("llm_model") or DEFAULT_LLM),
        embed_model_name=str(cfg.get("embed_model") or DEFAULT_EMBED),
        ollama_base_url=str(cfg.get("ollama_url") or OLLAMA_URL),
    )

    if req.force:
        rag.reset()

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

    inserted_chunks = 0
    skipped_files = 0

    for path in sorted(all_files):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            text = _read_pdf(path)
        else:
            text = _read_text(path)

        if not text.strip():
            skipped_files += 1
            continue

        rel_source = os.path.relpath(path, DOCUMENTS_DIR)
        header = f"[SOURCE FILE: {rel_source}]\n\n"
        chunks = _chunk_text(header + text)

        for c in chunks:
            await rag.ainsert(c, meta={"source": rel_source})
            inserted_chunks += 1

    cfg["folders"] = folders
    _save_db_config(req.name, cfg)

    # ✅ write once at the end
    try:
        rag.flush()
    except Exception:
        pass

    return {
        "ok": True,
        "status": "Database built",
        "db": req.name,
        "folders": folders,
        "files_found": len(all_files),
        "skipped_files": skipped_files,
        "inserted_chunks": inserted_chunks,
        "stats": rag.stats(),
    }


@router.post("/api/databases/chat")
async def database_chat(req: ChatRequest):
    try:
        cfg = _load_db_config(req.db)
        rag = LightRAG(
            working_dir=_db_workdir(req.db),
            llm_model_name=str(cfg.get("llm_model") or DEFAULT_LLM),
            embed_model_name=str(cfg.get("embed_model") or DEFAULT_EMBED),
            ollama_base_url=str(cfg.get("ollama_url") or OLLAMA_URL),
        )
        return await rag.aquery(req.query, param=QueryParam(mode="hybrid", top_k=5))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))