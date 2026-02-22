import os
import shutil
from typing import List, Optional

import asyncio
import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from pypdf import PdfReader  # <-- NEW

from lightrag import LightRAG, QueryParam
from lightrag.utils import setup_logger, wrap_embedding_func_with_attrs
from lightrag.llm.ollama import ollama_model_complete, ollama_embed

setup_logger("lightrag", level="INFO")

router = APIRouter(tags=["simulator"])

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.dirname(BACKEND_DIR)                     # Website/
PROJECT_ROOT = os.path.dirname(WEBSITE_DIR)                    # AURA/
DEFAULT_DOCS_DIR = os.path.join(PROJECT_ROOT, "ECEN_214_Docs") # AURA/ECEN_214_Docs

# Prefer env var, fallback to AURA/ECEN_214_Docs
DOCS_DIR = os.path.abspath(os.getenv("AURA_DOCS_DIR", DEFAULT_DOCS_DIR))

STORAGE_DIR = os.path.join(BACKEND_DIR, "storage")
RAG_WORKDIR = os.path.join(STORAGE_DIR, "rag_workdir")

LLM_MODEL = os.getenv("AURA_LLM_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("AURA_EMBED_MODEL", "nomic-embed-text")


def _ensure_dirs():
    os.makedirs(RAG_WORKDIR, exist_ok=True)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


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


def _chunk_text(text: str, max_chars: int = 2400, overlap: int = 250) -> List[str]:
    """
    Simple chunker so we don't shove massive PDFs into a single insert.
    """
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


@wrap_embedding_func_with_attrs(
    embedding_dim=768,
    max_token_size=8192,
    model_name=EMBED_MODEL,
)
async def embedding_func(texts: List[str]) -> np.ndarray:
    return await ollama_embed.func(texts, embed_model=EMBED_MODEL)


_rag: Optional[LightRAG] = None
_lock = asyncio.Lock()


async def get_rag() -> LightRAG:
    global _rag
    async with _lock:
        if _rag is not None:
            return _rag

        _ensure_dirs()
        _rag = LightRAG(
            working_dir=RAG_WORKDIR,
            llm_model_func=ollama_model_complete,
            llm_model_name=LLM_MODEL,
            embedding_func=embedding_func,
        )
        await _rag.initialize_storages()
        return _rag


class ChatRequest(BaseModel):
    query: str


@router.post("/api/chat")
async def chat(req: ChatRequest):
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        rag = await get_rag()
        ans = await rag.aquery(q, param=QueryParam(mode="hybrid"))
        return {"answer": str(ans), "sources": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Optional: keep upload, but NOT required if you index ECEN_214_Docs directly.
@router.post("/api/upload")
async def upload(files: List[UploadFile] = File(...)):
    # If you still want uploads, we store them into DOCS_DIR/uploads/
    upload_dir = os.path.join(DOCS_DIR, "_uploads")
    os.makedirs(upload_dir, exist_ok=True)

    saved = 0
    for f in files:
        out = os.path.join(upload_dir, f.filename)
        with open(out, "wb") as w:
            w.write(await f.read())
        saved += 1

    return {"status": f"Uploaded {saved} file(s) into {upload_dir}"}


@router.post("/api/build")
async def build(force_reload: bool = True):
    """
    Build LightRAG from DOCS_DIR (default: AURA/ECEN_214_Docs).
    PDFs are parsed into text and chunked.
    """
    if not os.path.exists(DOCS_DIR):
        raise HTTPException(status_code=400, detail=f"DOCS_DIR not found: {DOCS_DIR}")

    # Gather files
    all_files = []
    for root, _, files in os.walk(DOCS_DIR):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in [".pdf", ".txt", ".md"]:
                all_files.append(os.path.join(root, name))

    if not all_files:
        raise HTTPException(status_code=400, detail=f"No .pdf/.txt/.md files found in {DOCS_DIR}")

    try:
        global _rag

        if force_reload and os.path.exists(RAG_WORKDIR):
            shutil.rmtree(RAG_WORKDIR)
        os.makedirs(RAG_WORKDIR, exist_ok=True)

        async with _lock:
            _rag = None

        rag = await get_rag()

        inserted_chunks = 0
        skipped_files = 0

        for path in all_files:
            ext = os.path.splitext(path)[1].lower()

            if ext == ".pdf":
                text = _read_pdf(path)
            else:
                text = _read_text(path)

            if not text.strip():
                skipped_files += 1
                continue

            # Add filename header so the model “knows” where content came from
            header = f"[SOURCE FILE: {os.path.relpath(path, DOCS_DIR)}]\n\n"
            chunks = _chunk_text(header + text)

            for c in chunks:
                await rag.ainsert(c)
                inserted_chunks += 1

        return {
            "status": "LightRAG database built",
            "docs_dir": DOCS_DIR,
            "files_found": len(all_files),
            "skipped_files": skipped_files,
            "inserted_chunks": inserted_chunks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/docs-dir")
async def docs_dir():
    return {"docs_dir": DOCS_DIR}