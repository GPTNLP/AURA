# backend/lightrag_local.py
from __future__ import annotations

import os
import json
import time
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import urllib.request

import chromadb
from chromadb.config import Settings


@dataclass
class QueryParam:
    mode: str = "hybrid"
    top_k: int = 8


def _now_ms() -> int:
    return int(time.time() * 1000)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


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

    async def embed(self, text: str, timeout_s: float = 30.0) -> np.ndarray:
        payload = {"model": self.embed_model, "prompt": text}
        try:
            out = await asyncio.to_thread(self._post_json, "/api/embeddings", payload, timeout_s)
        except Exception as e:
            raise RuntimeError(f"Ollama embeddings failed at {self.base_url} ({e})")

        emb = out.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise RuntimeError("Ollama embeddings returned no embedding vector.")
        return np.array(emb, dtype=np.float32)

    async def generate(self, prompt: str, system: str = "", timeout_s: float = 180.0) -> str:
        # IMPORTANT: limit output + context so you don't time out / hang
        payload = {
            "model": self.llm_model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 300,   # cap output tokens-ish
                "num_ctx": 4096,      # cap context window
            },
        }
        try:
            out = await asyncio.to_thread(self._post_json, "/api/generate", payload, timeout_s)
        except Exception as e:
            raise RuntimeError(f"Ollama generate failed at {self.base_url} ({e})")

        txt = out.get("response")
        if not isinstance(txt, str):
            raise RuntimeError("Ollama generate returned no response text.")
        return txt.strip()


class LightRAG:
    """
    Chroma-backed persistent chunk store:
      - working_dir/chroma_db/  (persistent)
      - collection: "chunks" (cosine space)
    """

    def __init__(
        self,
        working_dir: str,
        llm_model_name: str,
        embed_model_name: str,
        ollama_base_url: str = "http://127.0.0.1:11434",
    ):
        self.working_dir = os.path.abspath(working_dir)
        os.makedirs(self.working_dir, exist_ok=True)

        self.client = OllamaClient(
            base_url=ollama_base_url,
            embed_model=embed_model_name,
            llm_model=llm_model_name,
        )

        self.chroma_path = os.path.join(self.working_dir, "chroma_db")
        os.makedirs(self.chroma_path, exist_ok=True)

        self.chroma = chromadb.PersistentClient(
            path=self.chroma_path,
            settings=Settings(anonymized_telemetry=False),
        )

        # cosine similarity
        self.col = self.chroma.get_or_create_collection(
            name="chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def reset(self):
        # delete + recreate
        try:
            self.chroma.delete_collection("chunks")
        except Exception:
            pass
        self.col = self.chroma.get_or_create_collection(
            name="chunks",
            metadata={"hnsw:space": "cosine"},
        )

    def stats(self) -> Dict[str, Any]:
        return {
            "chunk_count": self.col.count(),
            "vdb_path": self.chroma_path,
        }

    async def ainsert(self, text: str, meta: Optional[Dict[str, Any]] = None):
        meta = meta or {}
        emb = await self.client.embed(text)

        _id = f"chunk_{_now_ms()}"
        self.col.add(
            ids=[_id],
            documents=[text],
            embeddings=[emb.tolist()],
            metadatas=[meta],
        )

    async def aquery(self, query: str, param: Optional[QueryParam] = None) -> Dict[str, Any]:
        param = param or QueryParam()
        if self.col.count() == 0:
            return {"answer": "Database is empty. Build the database first.", "sources": [], "hits": []}

        q_emb = await self.client.embed(query)

        res = self.col.query(
            query_embeddings=[q_emb.tolist()],
            n_results=max(1, int(param.top_k)),
            include=["documents", "metadatas", "distances"],
        )

        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        hits = []
        sources = []
        ctx_parts = []

        for doc, meta, dist in zip(docs, metas, dists):
            # for cosine in chroma, "distance" is (1 - cosine_similarity) typically
            score = 1.0 - float(dist)
            hits.append({"score": score, "text": doc or "", "meta": meta or {}})
            ctx_parts.append(doc or "")

            src = (meta or {}).get("source")
            if isinstance(src, str) and src and src not in sources:
                sources.append(src)

        # Keep context bounded so Ollama doesn't stall
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