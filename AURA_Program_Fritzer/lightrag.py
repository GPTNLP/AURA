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
    """
    Lightweight RAG wrapper enhancing standard RAG with:
    - retrieve top-K documents via db retriever
    - simple rerank (heuristic on score + doc length)
    - assemble evidence-first prompt and call llm
    - compute cheap overlap evidence scores and return structured output
    """

    def __init__(self, llm, db, top_k: int = LIGHTRAG_K):
        self.llm = llm
        self.db = db
        self.top_k = top_k
    
    def retrieve(self, query: str) -> List[Tuple[Document, float]]:
        """Retrieve documents with relevance scores"""
        results = self.db.similarity_search_with_relevance_scores(query, k=self.top_k)
        return results
    
    def rerank(self, docs_with_scores: List[Tuple[Document, float]]) -> List[Tuple[Document, float]]:
        """Rerank by adjusting scores based on document length"""
        reranked = []
        for doc, score in docs_with_scores:
            length_bonus = min(0.1, len(doc.page_content) / 10000 * 0.1)
            adjusted_score = score + length_bonus
            reranked.append((doc, adjusted_score))
        
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked
    
    def build_prompt(self, query: str, docs_with_scores: List[Tuple[Document, float]]) -> str:
        """Build evidence-based prompt"""
        evidence_parts = []
        
        for i, (doc, score) in enumerate(docs_with_scores, 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "?")
            content = doc.page_content
            
            evidence_parts.append(
                f"Evidence {i} (Score: {score:.3f})\n"
                f"Source: {source}, Page {page}\n"
                f"{content}"
            )
        
        evidence = "\n\n---\n\n".join(evidence_parts)
        return LIGHTRAG_PROMPT.format(evidence=evidence, question=query)
    
    def compute_overlap(self, answer: str, docs_with_scores: List[Tuple[Document, float]]) -> List[Dict[str, Any]]:
        """Calculate word overlap between answer and evidence"""
        answer_words = set(answer.lower().split())
        
        evidence_list = []
        for i, (doc, score) in enumerate(docs_with_scores, 1):
            doc_words = set(doc.page_content.lower().split())
            overlap = len(answer_words & doc_words)
            total = len(answer_words | doc_words)
            overlap_score = overlap / total if total > 0 else 0
            
            evidence_list.append({
                "id": i,
                "source": doc.metadata.get("source", "Unknown"),
                "page": doc.metadata.get("page", "?"),
                "retrieval_score": score,
                "overlap_score": overlap_score
            })
        
        evidence_list.sort(key=lambda x: x["overlap_score"], reverse=True)
        return evidence_list
    
    def generate(self, query: str) -> Dict[str, Any]:
        """Generate answer with enhanced retrieval"""
        print("\nRetrieving relevant documents...")
        docs_with_scores = self.retrieve(query)
        
        if not docs_with_scores:
            return {
                "answer": "No relevant information found in the documents.",
                "evidence": [],
                "sources": []
            }
        
        print(f"Found {len(docs_with_scores)} documents")
        print("Reranking and generating answer...")
        
        reranked = self.rerank(docs_with_scores)
        prompt = self.build_prompt(query, reranked)
        
        response = self.llm.invoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
        
        print("Computing evidence contributions...")
        evidence = self.compute_overlap(answer, reranked)
        
        sources = [
            f"{doc.metadata.get('source', 'Unknown')} (Page {doc.metadata.get('page', '?')})"
            for doc, _ in reranked
        ]
        
        return {
            "answer": answer,
            "evidence": evidence,
            "sources": sources
        }