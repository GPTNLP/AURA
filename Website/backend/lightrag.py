"""
Retrieval augmented Generation system based on LightRAG paper:
https://arxiv.org/abs/2410.05779

Provides:
- LightRAG Class

This is a fairly simplified implementation of the above research paper + github focusing on
Enhancing retrieval via scoring, simple reranking based on relevance scoring, Evidence-based answer
generation, & overlap scoring for transparency.
"""

import json
import networkx as nx
from typing import List, Dict, Any
from langchain_core.documents import Document

class LightRAG:
    def __init__(self, llm, vector_db):
        self.llm = llm
        self.vector_db = vector_db
        self.graph_db = nx.Graph()

    # ==========================================
    # PHASE 1: GRAPH-BASED TEXT INDEXING
    # ==========================================
    def build_index(self, chunks: List[Document]):
        """
        Processes text chunks into a searchable graph and vector structure.
        """
        for chunk in chunks:
            # 1. Extract Entities and Relationships using LLM
            raw_graph_data = self._extract_entities_and_relations(chunk.page_content)
            
            # 2. Parse the LLM output and insert into GraphDB
            self._parse_and_insert_graph_data(raw_graph_data)
            
        # 3. Vector Indexing: Profile the graph elements into the Vector DB
        self._profile_and_embed_graph()

    def _extract_entities_and_relations(self, text_chunk: str) -> str:
        """Prompts the LLM to find entities (nodes) and relations (edges)."""
        prompt = f"""
        -Goal-
        Given a text document that is potentially relevant to this activity and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.
        
        -Steps-
        1. Identify all entities. For each identified entity, extract the following information:
        - entity_name: Name of the entity, capitalized
        - entity_type: One of the following types: [organization, person, geo, event, concept]
        - entity_description: Comprehensive description of the entity's attributes and activities
        Format each entity as ("entity"|"<entity_name>"|"<entity_type>"|"<entity_description>")
        
        2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
        For each pair of related entities, extract the following information:
        - source_entity: name of the source entity, as identified in step 1
        - target_entity: name of the target entity, as identified in step 1
        - relationship_description: explanation as to why you think the source entity and the target entity are related to each other
        - relationship_keywords: one or more high-level key words that summarize the overarching nature of the relationship
        Format each relationship as ("relationship"|"<source_entity>"|"<target_entity>"|"<relationship_description>"|"<relationship_keywords>")
        
        3. Return output in English as a single list of all the entities and relationships identified in steps 1 and 2. Use "##" as the list delimiter.
        
        -Real Data-
        Text: {text_chunk}
        Output:
        """
        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _parse_and_insert_graph_data(self, raw_data: str):
        """Parses the ## delimited output and populates the NetworkX graph."""
        items = raw_data.split("##")
        for item in items:
            item = item.strip().strip('()')
            parts = [p.strip('"') for p in item.split('"|"')]
            
            if len(parts) > 0 and parts[0] == "entity" and len(parts) == 4:
                _, name, e_type, desc = parts
                # Deduplication happens naturally in NetworkX if the node name already exists
                if self.graph_db.has_node(name):
                    # Append new context to existing description
                    self.graph_db.nodes[name]['description'] += f" {desc}"
                else:
                    self.graph_db.add_node(name, type=e_type, description=desc)
                    
            elif len(parts) > 0 and parts[0] == "relationship" and len(parts) == 5:
                _, src, tgt, desc, keywords = parts
                if self.graph_db.has_edge(src, tgt):
                    self.graph_db[src][tgt]['description'] += f" {desc}"
                else:
                    self.graph_db.add_edge(src, tgt, description=desc, keywords=keywords)

    def _profile_and_embed_graph(self):
        """Generates key-value pairs for the graph and pushes to ChromaDB."""
        texts = []
        metadatas = []
        
        # Profile Nodes
        for node, data in self.graph_db.nodes(data=True):
            texts.append(f"Entity: {node}. Type: {data.get('type')}. Description: {data.get('description')}")
            metadatas.append({"type": "entity", "key": node})
            
        # Profile Edges
        for u, v, data in self.graph_db.edges(data=True):
            texts.append(f"Relationship between {u} and {v}. Keywords: {data.get('keywords')}. Description: {data.get('description')}")
            metadatas.append({"type": "relation", "key": f"{u}-{v}"})
            
        if texts:
            self.vector_db.add_texts(texts=texts, metadatas=metadatas)

    # ==========================================
    # PHASE 2: DUAL-LEVEL RETRIEVAL PARADIGM
    # ==========================================
    def retrieve(self, query: str) -> str:
        """Retrieves context using local and global keys, plus graph neighbors."""
        
        # 1. Keyword Extraction
        keywords = self._extract_query_keywords(query)
        local_keys = keywords.get("low_level_keywords", [])
        global_keys = keywords.get("high_level_keywords", [])
        
        retrieved_texts = []
        retrieved_nodes = set()
        
        # 2. Match local keys (Entities) and global keys (Relationships) in Vector DB
        for key in local_keys + global_keys:
            docs = self.vector_db.similarity_search(key, k=2)
            for d in docs:
                retrieved_texts.append(d.page_content)
                if d.metadata.get("type") == "entity":
                    retrieved_nodes.add(d.metadata.get("key"))
                elif d.metadata.get("type") == "relation":
                    u, v = d.metadata.get("key", "-").split("-", 1)
                    retrieved_nodes.update([u, v])
                    
        # 3. High-Order Relatedness (Graph DB 1-hop neighbors)
        neighbor_texts = []
        for node in retrieved_nodes:
            if self.graph_db.has_node(node):
                for neighbor in self.graph_db.neighbors(node):
                    edge_data = self.graph_db[node][neighbor]
                    neighbor_texts.append(
                        f"Related Entity: {neighbor}. Connection: {edge_data.get('description')}"
                    )
                    
        # Combine all context
        full_context = "\n".join(list(set(retrieved_texts + neighbor_texts)))
        return full_context

    def _extract_query_keywords(self, query: str) -> dict:
        """Extracts local and global keywords using the LLM."""
        prompt = f"""
        -Role-
        You are a helpful assistant tasked with identifying both high-level and low-level keywords in the user's query.
        
        -Goal-
        Given the query, list both high-level and low-level keywords. High-level keywords focus on overarching concepts or themes, while low-level keywords focus on specific entities, details, or concrete terms.
        
        Output the keywords in strict JSON format with exactly two keys: "high_level_keywords" (list of strings) and "low_level_keywords" (list of strings).
        
        -Real Data-
        Query: {query}
        Output:
        """
        response = self.llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        
        try:
            # Clean up potential markdown formatting from local LLMs
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except json.JSONDecodeError:
            print("Failed to parse JSON from LLM keyword extraction.")
            return {"high_level_keywords": [query], "low_level_keywords": []}

    # ==========================================
    # PHASE 3: ANSWER GENERATION
    # ==========================================
    def generate(self, query: str) -> Dict[str, Any]:
        """Generates the final answer using the retrieved graph context."""
        context = self.retrieve(query)
        
        prompt = f"""Based on the following retrieved entities, relationships, and context, answer the user's query comprehensively.
        
        Context:
        {context}
        
        Query: {query}
        Answer:"""
        
        response = self.llm.invoke(prompt)
        
        return {
            "answer": response.content if hasattr(response, "content") else str(response),
            "context_used": context
        }