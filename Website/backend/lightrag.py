"""
Retrieval augmented Generation system based on LightRAG paper:
https://arxiv.org/abs/2410.05779

Provides:
- LightRAG Class

This is a fairly simplified implementation of the above research paper + github focusing on
Enhancing retrieval via scoring, simple reranking based on relevance scoring, Evidence-based answer
generation, & overlap scoring for transparency.
"""

from typing import List, Dict, Any, Tuple
from langchain_core.documents import Document
from config import LIGHTRAG_K, LIGHTRAG_PROMPT

class LightRAG:
    def __init__(self, llm, db, top_k: int = LIGHTRAG_K):
        self.llm = llm
        self.db = db
        self.top_k = top_k
    
    def retrieve(self, query: str) -> List[Tuple[Document, float]]:
        """Retrieve documents with relevance scores."""
        # Silence potential Chroma warnings
        return self.db.similarity_search_with_relevance_scores(query, k=self.top_k)
    
    def rerank(self, docs_with_scores: List[Tuple[Document, float]]) -> List[Tuple[Document, float]]:
        """Heuristic Reranking based on content length."""
        reranked = []
        for doc, score in docs_with_scores:
            # Small boost for detailed sections (max 0.1 boost)
            length_bonus = min(0.1, len(doc.page_content) / 10000.0)
            reranked.append((doc, score + length_bonus))
        
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked
    
    def build_prompt(self, query: str, docs_with_scores: List[Tuple[Document, float]]) -> str:
        """Construct the prompt."""
        evidence_blocks = []
        for i, (doc, score) in enumerate(docs_with_scores, 1):
            source = os.path.basename(doc.metadata.get("source", "Unknown"))
            page = doc.metadata.get("page", "?")
            evidence_blocks.append(
                f"[Evidence {i}] (Relevance: {score:.2f})\n"
                f"Source: {source} | Page: {page}\n"
                f"{doc.page_content}"
            )
        
        evidence_text = "\n\n".join(evidence_blocks)
        return LIGHTRAG_PROMPT.format(evidence=evidence_text, question=query)
    
    def compute_overlap(self, answer: str, docs: List[Tuple[Document, float]]) -> List[Dict[str, Any]]:
        """Compute basic word overlap confidence."""
        answer_words = set(answer.lower().split())
        evidence_list = []
        
        for i, (doc, score) in enumerate(docs, 1):
            doc_words = set(doc.page_content.lower().split())
            if not doc_words: continue
                
            intersection = len(answer_words & doc_words)
            union = len(answer_words | doc_words)
            overlap_score = intersection / union if union > 0 else 0
            
            if overlap_score > 0.01:
                evidence_list.append({
                    "id": i,
                    "source": os.path.basename(doc.metadata.get("source", "Unknown")),
                    "page": doc.metadata.get("page", "?"),
                    "retrieval_score": score,
                    "overlap_score": overlap_score
                })
        
        evidence_list.sort(key=lambda x: x["overlap_score"], reverse=True)
        return evidence_list
    
    def generate(self, query: str) -> Dict[str, Any]:
        """Execute the LightRAG pipeline."""
        docs = self.retrieve(query)
        
        if not docs:
            return {
                "answer": "I could not find any relevant documents to answer your question.",
                "evidence": [],
                "sources": []
            }
        
        reranked_docs = self.rerank(docs)
        prompt = self.build_prompt(query, reranked_docs)
        
        # Direct invoke, no chains
        response = self.llm.invoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
        
        evidence_data = self.compute_overlap(answer, reranked_docs)
        sources = [
            f"{os.path.basename(doc.metadata.get('source', 'Unknown'))} (p.{doc.metadata.get('page', '?')})"
            for doc, _ in reranked_docs
        ]
        
        return {
            "answer": answer,
            "evidence": evidence_data,
            "sources": sources
        }