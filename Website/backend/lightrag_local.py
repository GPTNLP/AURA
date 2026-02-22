# Website/backend/lightrag_local.py
"""
Local LightRAG-like system (simple + practical for your project)

- Uses:
  1) Chunking + embeddings into a tiny local vector store
  2) Retrieval
  3) Optional graph extraction later (you can keep your Phase 1 idea)

This version adds:
- QueryParam (so simulator_api can pass mode)
- aquery() method used by your API
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class QueryParam:
    mode: str = "hybrid"  # placeholder for future


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


class SimpleVectorDB:
    """
    Very small local vector store:
    - add_text(text, meta, embedding)
    - search(query_embedding, k)
    """
    def __init__(self):
        self._rows: List[Tuple[str, Dict[str, Any], np.ndarray]] = []

    def add(self, text: str, meta: Dict[str, Any], emb: np.ndarray):
        self._rows.append((text, meta, emb.astype(np.float32)))

    def search(self, q_emb: np.ndarray, k: int = 6) -> List[Dict[str, Any]]:
        if not self._rows:
            return []
        scored = []
        for text, meta, emb in self._rows:
            scored.append((_cosine_sim(q_emb, emb), text, meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, text, meta in scored[:k]:
            out.append({"score": score, "text": text, "meta": meta})
        return out


class LightRAG:
    """
    Minimal RAG wrapper that matches what the simulator needs:
    - ainsert(text) : embed + store
    - aquery(query) : retrieve top chunks + ask LLM
    """

    def __init__(self, llm_client, embed_client, vector_db: Optional[SimpleVectorDB] = None):
        self.llm = llm_client
        self.embed = embed_client
        self.vdb = vector_db or SimpleVectorDB()

    async def ainsert(self, text: str, meta: Optional[Dict[str, Any]] = None):
        meta = meta or {}
        emb = await self.embed.embed(text)
        self.vdb.add(text=text, meta=meta, emb=emb)

    async def aquery(self, query: str, param: Optional[QueryParam] = None) -> Dict[str, Any]:
        # embed query
        q_emb = await self.embed.embed(query)

        # retrieve
        hits = self.vdb.search(q_emb, k=8)
        context = "\n\n---\n\n".join([h["text"] for h in hits])

        # ask LLM
        answer = await self.llm.complete(
            system="You are AURA. Answer using the provided context. If context is missing, say you don't have enough info.",
            prompt=f"CONTEXT:\n{context}\n\nQUESTION:\n{query}\n\nANSWER:"
        )

        sources = []
        for h in hits[:6]:
            if isinstance(h.get("meta"), dict) and h["meta"].get("source"):
                sources.append(str(h["meta"]["source"]))

        return {"answer": answer, "sources": sources, "hits": hits}