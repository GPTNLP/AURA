# backend/lightrag_local.py
"""
Lightweight persistent RAG store + Ollama client (no chroma/langchain)

- Stores chunks in: <working_dir>/vdb_chunks.json
- Embeddings via Ollama: POST {ollama_base_url}/api/embeddings
- Chat completion via Ollama: POST {ollama_base_url}/api/generate

This matches database_api.py usage:
- LightRAG(working_dir=..., llm_model_name=..., embed_model_name=..., ollama_base_url=...)
- await ainsert(text, meta)
- await aquery(query, param=QueryParam(...))
- stats()
- reset()
"""

from __future__ import annotations

import os
import json
import random
import time
import math
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import urllib.request


# -------------------------
# Query params
# -------------------------
@dataclass
class QueryParam:
    mode: str = "hybrid"
    top_k: int = 5


# -------------------------
# Helpers
# -------------------------
def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_mkdir(path: str):
    os.makedirs(path, exist_ok=True)


def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, obj):
    """
    Windows-safe JSON save.

    - Writes to tmp file first
    - Tries atomic replace
    - If Windows locks the destination, retries
    - If still locked, falls back to writing directly (non-atomic)
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"

    data = json.dumps(obj, ensure_ascii=False, indent=2)

    # write tmp
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)

    # try atomic replace with retries (Windows lock issues)
    for attempt in range(12):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            # someone is holding the destination file open
            time.sleep(0.05 + random.random() * 0.15)

    # last resort: write directly (non-atomic)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
    finally:
        # cleanup tmp if it still exists
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


# -------------------------
# Ollama HTTP client (with timeouts)
# -------------------------
class OllamaClient:
    def __init__(self, base_url: str, embed_model: str, llm_model: str):
        self.base_url = (base_url or "http://127.0.0.1:11434").rstrip("/")
        self.embed_model = embed_model
        self.llm_model = llm_model

    def _post_json(self, path: str, payload: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw) if raw else {}

    async def embed(self, text: str, timeout_s: float = 15.0) -> np.ndarray:
        # Run blocking urllib in a thread so FastAPI doesn't freeze the event loop
        payload = {"model": self.embed_model, "prompt": text}
        try:
            out = await asyncio.to_thread(self._post_json, "/api/embeddings", payload, timeout_s)
        except Exception as e:
            raise RuntimeError(
                f"Ollama embeddings failed. Is Ollama running at {self.base_url}? ({e})"
            )
        emb = out.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise RuntimeError("Ollama embeddings returned no embedding vector.")
        return np.array(emb, dtype=np.float32)

    async def generate(self, prompt: str, system: str = "", timeout_s: float = 180.0) -> str:
        payload = {
            "model": self.llm_model,
            "prompt": prompt,
            "system": system,
            "stream": False,
        }
        try:
            out = await asyncio.to_thread(self._post_json, "/api/generate", payload, timeout_s)
        except Exception as e:
            raise RuntimeError(
                f"Ollama generate failed. Is Ollama running at {self.base_url}? ({e})"
            )
        txt = out.get("response")
        if not isinstance(txt, str):
            raise RuntimeError("Ollama generate returned no response text.")
        return txt.strip()


# -------------------------
# LightRAG persistent store
# -------------------------
class LightRAG:
    def __init__(
        self,
        working_dir: str,
        llm_model_name: str,
        embed_model_name: str,
        ollama_base_url: str = "http://127.0.0.1:11434",
    ):
        self.working_dir = os.path.abspath(working_dir)
        _safe_mkdir(self.working_dir)

        self.vdb_path = os.path.join(self.working_dir, "vdb_chunks.json")
        self.client = OllamaClient(
            base_url=ollama_base_url,
            embed_model=embed_model_name,
            llm_model=llm_model_name,
        )

        # rows: [{"id":..., "text":..., "meta":..., "embedding":[...]}]
        self._rows: List[Dict[str, Any]] = _load_json(self.vdb_path, default=[])

        # cache numpy embeddings for fast search
        self._emb_cache: List[np.ndarray] = []
        for r in self._rows:
            emb = r.get("embedding")
            if isinstance(emb, list) and emb:
                self._emb_cache.append(np.array(emb, dtype=np.float32))
            else:
                self._emb_cache.append(np.zeros((1,), dtype=np.float32))

    def reset(self):
        self._rows = []
        self._emb_cache = []
        _save_json(self.vdb_path, self._rows)

    def stats(self) -> Dict[str, Any]:
        return {
            "chunk_count": len(self._rows),
            "vdb_path": self.vdb_path,
        }
    

    async def ainsert(self, text: str, meta: Optional[Dict[str, Any]] = None):
        # mark dirty; save later via flush()
        self._dirty = True
        meta = meta or {}

        emb = await self.client.embed(text)
        row = {
            "id": f"chunk_{_now_ms()}_{len(self._rows)}",
            "text": text,
            "meta": meta,
            "embedding": emb.astype(np.float32).tolist(),
        }
        self._rows.append(row)
        self._emb_cache.append(emb.astype(np.float32))

    def flush(self):
        if getattr(self, "_dirty", False):
            _save_json(self.vdb_path, self._rows)
            self._dirty = False
            
    async def aquery(self, query: str, param: Optional[QueryParam] = None) -> Dict[str, Any]:
        param = param or QueryParam()
        if not self._rows:
            return {
                "answer": "Database is empty. Build the database first.",
                "sources": [],
                "hits": [],
            }

        q_emb = await self.client.embed(query)

        scored: List[Tuple[float, int]] = []
        for i, emb in enumerate(self._emb_cache):
            if emb.size < 8:
                continue
            scored.append((_cosine_sim(q_emb, emb), i))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[: max(1, int(param.top_k))]

        hits = []
        sources = []
        ctx_parts = []

        for score, idx in top:
            r = self._rows[idx]
            hits.append({"score": score, "text": r.get("text", ""), "meta": r.get("meta", {})})
            ctx_parts.append(r.get("text", ""))

            m = r.get("meta") or {}
            src = m.get("source")
            if isinstance(src, str) and src and src not in sources:
                sources.append(src)

        context = "\n\n---\n\n".join(ctx_parts)

        # Prevent massive prompts that make /api/generate slow/hang
        MAX_CTX_CHARS = 12000
        if len(context) > MAX_CTX_CHARS:
            context = context[:MAX_CTX_CHARS] + "\n\n[...context truncated...]"

        system = (
            "You are AURA. Answer ONLY using the provided context. "
            "If the context doesn't contain the answer, say you don't have enough information."
        )
        prompt = f"CONTEXT:\n{context}\n\nQUESTION:\n{query}\n\nANSWER:"

        answer = await self.client.generate(prompt=prompt, system=system)

        return {"answer": answer, "sources": sources, "hits": hits}