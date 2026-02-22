# backend/lightrag_local.py
from __future__ import annotations

import os
import json
import time
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import urllib.request

from rank_bm25 import BM25Okapi


# -------------------------
# Query params
# -------------------------
@dataclass
class QueryParam:
    mode: str = "hybrid"   # "vector" | "bm25" | "hybrid"
    top_k: int = 8


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


def _save_json_atomic(path: str, obj):
    _safe_mkdir(os.path.dirname(path))
    tmp = f"{path}.tmp"
    data = json.dumps(obj, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, path)


def _normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    norm = float(np.linalg.norm(v)) + 1e-12
    return (v / norm).astype(np.float32)


def _tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    out = []
    word = []
    for ch in s:
        if ch.isalnum():
            word.append(ch)
        else:
            if word:
                out.append("".join(word))
                word = []
    if word:
        out.append("".join(word))
    return out


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

    async def embed(self, text: str, timeout_s: float = 60.0) -> np.ndarray:
        payload = {"model": self.embed_model, "prompt": text}
        try:
            out = await asyncio.to_thread(self._post_json, "/api/embeddings", payload, timeout_s)
        except Exception as e:
            raise RuntimeError(f"Ollama embeddings failed. Is Ollama running at {self.base_url}? ({e})")

        emb = out.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise RuntimeError("Ollama embeddings returned no embedding vector.")
        return np.array(emb, dtype=np.float32)

    async def generate(self, prompt: str, system: str = "", timeout_s: float = 180.0) -> str:
        payload = {
            "model": self.llm_model,
            "prompt": prompt,
            "system": system,        # ✅ include system in request
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 300,
                "num_ctx": 4096,
            },
        }
        try:
            out = await asyncio.to_thread(self._post_json, "/api/generate", payload, timeout_s)
        except Exception as e:
            raise RuntimeError(f"Ollama generate failed. Is Ollama running at {self.base_url}? ({e})")

        txt = out.get("response")
        if not isinstance(txt, str):
            raise RuntimeError("Ollama generate returned no response text.")
        return txt.strip()


# -------------------------
# LightRAG persistent store (NumPy cosine + BM25)
# -------------------------
class LightRAG:
    """
    Persistent store in working_dir:
      - meta.json         (rows: id/text/meta)
      - embeddings.npy    (float32 normalized vectors)
    """

    def __init__(
        self,
        working_dir: str,
        llm_model_name: str,
        embed_model_name: str,
        ollama_base_url: str = "http://127.0.0.1:11434",
    ):
        self.working_dir = os.path.abspath(working_dir)
        _safe_mkdir(self.working_dir)

        self.meta_path = os.path.join(self.working_dir, "meta.json")
        self.emb_path = os.path.join(self.working_dir, "embeddings.npy")

        self.client = OllamaClient(
            base_url=ollama_base_url,
            embed_model=embed_model_name,
            llm_model=llm_model_name,
        )

        # rows: [{"id":..., "text":..., "meta":...}]
        self._rows: List[Dict[str, Any]] = _load_json(self.meta_path, default=[])

        # embeddings: (N, D) normalized float32
        self._emb: Optional[np.ndarray] = None

        # bm25
        self._bm25: Optional[BM25Okapi] = None
        self._bm25_tokens: List[List[str]] = []

        self._load_store()

    def _load_store(self):
        if os.path.exists(self.emb_path):
            try:
                self._emb = np.load(self.emb_path).astype(np.float32)
            except Exception:
                self._emb = None

        # if mismatch, discard embeddings
        if self._emb is None or self._emb.ndim != 2 or self._emb.shape[0] != len(self._rows):
            self._emb = None

        # build bm25
        self._bm25_tokens = [_tokenize(r.get("text", "")) for r in self._rows]
        self._bm25 = BM25Okapi(self._bm25_tokens) if self._bm25_tokens else None

    def flush(self):
        _save_json_atomic(self.meta_path, self._rows)
        if self._emb is not None:
            np.save(self.emb_path, self._emb.astype(np.float32))

    def reset(self):
        self._rows = []
        self._emb = None
        self._bm25 = None
        self._bm25_tokens = []

        for p in [self.meta_path, self.emb_path]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

    def stats(self) -> Dict[str, Any]:
        return {
            "chunk_count": len(self._rows),
            "vdb_path": self.working_dir,   # ✅ your frontend expects vdb_path
        }

    async def ainsert(self, text: str, meta: Optional[Dict[str, Any]] = None):
        meta = meta or {}

        emb = await self.client.embed(text)
        emb = _normalize(emb)

        _id = f"chunk_{_now_ms()}_{len(self._rows)}"
        self._rows.append({"id": _id, "text": text, "meta": meta})

        if self._emb is None:
            self._emb = emb.reshape(1, -1)
        else:
            self._emb = np.vstack([self._emb, emb.reshape(1, -1)])

        # BM25 rebuild (fine for your scale)
        self._bm25_tokens = [_tokenize(r.get("text", "")) for r in self._rows]
        self._bm25 = BM25Okapi(self._bm25_tokens) if self._bm25_tokens else None

    def _search_vector(self, q_emb: np.ndarray, top_k: int) -> List[Tuple[int, float]]:
        if self._emb is None or len(self._rows) == 0:
            return []

        q = _normalize(q_emb).reshape(1, -1)      # (1, D)
        # cosine similarity since both normalized
        sims = (self._emb @ q.T).reshape(-1)      # (N,)
        k = max(1, int(top_k))
        if sims.shape[0] <= k:
            idxs = np.argsort(-sims)
        else:
            # partial topk (faster)
            idxs = np.argpartition(-sims, kth=k-1)[:k]
            idxs = idxs[np.argsort(-sims[idxs])]

        return [(int(i), float(sims[i])) for i in idxs]

    def _search_bm25(self, query: str, top_k: int) -> List[Tuple[int, float]]:
        if self._bm25 is None or len(self._rows) == 0:
            return []
        toks = _tokenize(query)
        scores = self._bm25.get_scores(toks)
        k = max(1, int(top_k))
        idxs = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in idxs]

    async def aquery(self, query: str, param: Optional[QueryParam] = None) -> Dict[str, Any]:
        param = param or QueryParam()
        if len(self._rows) == 0:
            return {"answer": "Database is empty. Build the database first.", "sources": [], "hits": []}

        mode = (param.mode or "hybrid").lower()
        top_k = max(1, int(param.top_k))

        candidates: Dict[int, Dict[str, float]] = {}

        if mode in ("vector", "hybrid"):
            q_emb = await self.client.embed(query)
            for idx, score in self._search_vector(q_emb, top_k=top_k * 3):
                candidates.setdefault(idx, {})
                candidates[idx]["vec"] = score  # cosine sim ~[-1..1] usually [0..1] for embeddings

        if mode in ("bm25", "hybrid"):
            for idx, score in self._search_bm25(query, top_k=top_k * 3):
                candidates.setdefault(idx, {})
                candidates[idx]["bm25"] = score

        # combine scores
        scored: List[Tuple[float, int]] = []
        for idx, d in candidates.items():
            vec = float(d.get("vec", 0.0))
            bm = float(d.get("bm25", 0.0))
            # squash bm25 so it doesn’t dominate
            bm_norm = bm / (abs(bm) + 8.0)

            if mode == "hybrid":
                total = (0.75 * vec) + (0.25 * bm_norm)
            elif mode == "vector":
                total = vec
            else:
                total = bm_norm

            scored.append((float(total), int(idx)))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        hits = []
        sources = []
        ctx_parts = []

        for score, idx in top:
            r = self._rows[idx]
            hits.append({"score": score, "text": r.get("text", ""), "meta": r.get("meta", {})})
            ctx_parts.append(r.get("text", ""))

            src = (r.get("meta") or {}).get("source")
            if isinstance(src, str) and src and src not in sources:
                sources.append(src)

        context = "\n\n---\n\n".join(ctx_parts)
        MAX_CTX_CHARS = 12000
        if len(context) > MAX_CTX_CHARS:
            context = context[:MAX_CTX_CHARS] + "\n\n[...context truncated...]"

        system = (
            "You are AURA. Answer ONLY using the provided context. "
            "If the context doesn't contain the answer, say you don't have enough information."
        )
        prompt = f"CONTEXT:\n{context}\n\nQUESTION:\n{query}\n\nANSWER:"
        answer = await self.client.generate(prompt=prompt, system=system, timeout_s=180.0)

        return {"answer": answer, "sources": sources, "hits": hits}