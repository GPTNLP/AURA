# Website/backend/simulator_api.py
import os
import json
import shutil
import asyncio
from typing import List, Optional, Dict, Any

import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader

from lightrag_local import LightRAG, QueryParam

router = APIRouter(tags=["simulator"])

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.dirname(BACKEND_DIR)                     # Website/
PROJECT_ROOT = os.path.dirname(WEBSITE_DIR)                    # AURA/
DEFAULT_DOCS_DIR = os.path.join(PROJECT_ROOT, "ECEN_214_Docs") # AURA/ECEN_214_Docs

DOCS_DIR = os.path.abspath(os.getenv("AURA_DOCS_DIR", DEFAULT_DOCS_DIR))
STORAGE_DIR = os.path.join(BACKEND_DIR, "storage")
RAG_WORKDIR = os.path.join(STORAGE_DIR, "rag_workdir")

# Ollama server (already running on 11434 on your machine)
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434")
LLM_MODEL = os.getenv("AURA_LLM_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("AURA_EMBED_MODEL", "nomic-embed-text")


def _ensure_dirs():
    os.makedirs(RAG_WORKDIR, exist_ok=True)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_pdf(path: str) -> str:
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        if txt.strip():
            parts.append(txt)
    return "\n\n".join(parts)


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


class OllamaEmbedClient:
    def __init__(self, base: str, model: str):
        self.base = base
        self.model = model

    async def embed(self, text: str):
        # Ollama embeddings endpoint
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            r.raise_for_status()
            data = r.json()
            vec = data.get("embedding")
            if not vec:
                raise RuntimeError("Ollama returned no embedding")
            import numpy as np
            return np.array(vec, dtype=np.float32)


class OllamaLLMClient:
    def __init__(self, base: str, model: str):
        self.base = base
        self.model = model

    async def complete(self, system: str, prompt: str) -> str:
        # /api/generate returns streaming by default; set stream false
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(
                f"{self.base}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                },
            )
            r.raise_for_status()
            data = r.json()
            return (data.get("response") or "").strip()


_rag: Optional[LightRAG] = None
_lock = asyncio.Lock()


async def get_rag() -> LightRAG:
    global _rag
    async with _lock:
        if _rag is not None:
            return _rag

        _ensure_dirs()
        llm = OllamaLLMClient(OLLAMA_BASE, LLM_MODEL)
        emb = OllamaEmbedClient(OLLAMA_BASE, EMBED_MODEL)
        _rag = LightRAG(llm_client=llm, embed_client=emb)
        return _rag


class ChatRequest(BaseModel):
    query: str


@router.get("/api/docs-dir")
async def docs_dir():
    return {"docs_dir": DOCS_DIR}


@router.post("/api/chat")
async def chat(req: ChatRequest):
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Verify Ollama is reachable (nice error)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama not reachable at {OLLAMA_BASE}. {e}")

    rag = await get_rag()
    out = await rag.aquery(q, param=QueryParam(mode="hybrid"))
    return {"answer": out["answer"], "sources": out.get("sources", [])}


@router.post("/api/upload")
async def upload(files: List[UploadFile] = File(...)):
    # store uploads into DOCS_DIR/_uploads/
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
    Build local vector store from DOCS_DIR (default: AURA/ECEN_214_Docs).
    """
    if not os.path.exists(DOCS_DIR):
        raise HTTPException(status_code=400, detail=f"DOCS_DIR not found: {DOCS_DIR}")

    # Gather files
    all_files: List[str] = []
    for root, _, files in os.walk(DOCS_DIR):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in [".pdf", ".txt", ".md"]:
                all_files.append(os.path.join(root, name))

    if not all_files:
        raise HTTPException(status_code=400, detail=f"No .pdf/.txt/.md files found in {DOCS_DIR}")

    global _rag

    # reset local rag memory
    async with _lock:
        _rag = None

    rag = await get_rag()

    inserted_chunks = 0
    skipped_files = 0

    for path in all_files:
        ext = os.path.splitext(path)[1].lower()
        try:
            text = _read_pdf(path) if ext == ".pdf" else _read_text(path)
        except Exception:
            text = ""

        if not text.strip():
            skipped_files += 1
            continue

        rel = os.path.relpath(path, DOCS_DIR)
        header = f"[SOURCE FILE: {rel}]\n\n"
        chunks = _chunk_text(header + text)

        for c in chunks:
            await rag.ainsert(c, meta={"source": rel})
            inserted_chunks += 1

    return {
        "status": "Local RAG index built",
        "docs_dir": DOCS_DIR,
        "files_found": len(all_files),
        "skipped_files": skipped_files,
        "inserted_chunks": inserted_chunks,
        "ollama_base": OLLAMA_BASE,
        "llm_model": LLM_MODEL,
        "embed_model": EMBED_MODEL,
    }