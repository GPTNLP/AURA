import json
import re
import os
import networkx as nx
from networkx.algorithms.community import louvain_communities
from typing import List, Dict, Any
from langchain_core.documents import Document

class LightRAG:
    def __init__(self, llm, vector_db, graph_file_path: str):
        self.llm = llm
        self.vector_db = vector_db
        self.graph_file_path = graph_file_path
        
        # Load existing graph if it exists, otherwise create a new one
        if os.path.exists(self.graph_file_path):
            self.graph_db = nx.read_graphml(self.graph_file_path)
        else:
            self.graph_db = nx.Graph()

    # ==========================================
    # PHASE 1: GRAPH-BASED TEXT INDEXING
    # ==========================================
    def build_index(self, chunks: List[Document]):
        """Processes text chunks into a searchable graph and vector structure."""
        print(f"Extracting entities and relations from {len(chunks)} chunks...")
        for chunk in chunks:
            raw_graph_data = self._extract_entities_and_relations(chunk.page_content)
            self._parse_and_insert_graph_data(raw_graph_data)
            
        print("Resolving duplicate entities...")
        self._resolve_entities()
            
        print("Detecting communities and generating summaries...")
        self._build_and_summarize_communities()
        
        # Save the graph to disk so it can be deployed to the Nano
        nx.write_graphml(self.graph_db, self.graph_file_path)
        print("Graph indexing complete and saved.")

    def _extract_entities_and_relations(self, text_chunk: str) -> str:
        prompt = f"""
        Extract entities and relationships from the text.
        1. Entities: Format as ("entity"|"<Name>"|"<Type>"|"<Description>")
        2. Relationships: Format as ("relationship"|"<Source>"|"<Target>"|"<Description>"|"<Keywords>")
        Return as a single list delimited by "##".
        
        Text: {text_chunk}
        Output:
        """
        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _parse_and_insert_graph_data(self, raw_data: str):
        entity_pattern = re.compile(r'\(\s*"entity"\s*\|\s*"([^"]+)"\s*\|\s*"([^"]+)"\s*\|\s*"([^"]+)"\s*\)')
        relation_pattern = re.compile(r'\(\s*"relationship"\s*\|\s*"([^"]+)"\s*\|\s*"([^"]+)"\s*\|\s*"([^"]+)"\s*\|\s*"([^"]+)"\s*\)')
        
        for match in entity_pattern.finditer(raw_data):
            name, e_type, desc = match.groups()
            name = name.strip()
            if self.graph_db.has_node(name):
                self.graph_db.nodes[name]['description'] = str(self.graph_db.nodes[name].get('description', '')) + f" {desc}"
            else:
                self.graph_db.add_node(name, type=e_type, description=desc)
                
        for match in relation_pattern.finditer(raw_data):
            src, tgt, desc, keywords = match.groups()
            src, tgt = src.strip(), tgt.strip()
            if self.graph_db.has_edge(src, tgt):
                self.graph_db[src][tgt]['description'] = str(self.graph_db[src][tgt].get('description', '')) + f" {desc}"
            else:
                self.graph_db.add_edge(src, tgt, description=desc, keywords=keywords)

    def _resolve_entities(self):
        """Uses the LLM to find and merge semantically identical entities (e.g. 'Apple' and 'Apple Inc.')."""
        nodes = list(self.graph_db.nodes())
        if len(nodes) < 2: return
        
        # Pass nodes in batches to avoid overwhelming the LLM's context window
        batch_size = 50
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            prompt = f"""
            Identify entities that refer to the exact same concept or organization and should be merged.
            Output ONLY a strict JSON list of lists. Example: [["Apple", "Apple Inc."], ["Jetson Nano", "Nvidia Jetson Nano"]]
            Entities: {batch}
            Output:
            """
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            
            try:
                content = content.replace("```json", "").replace("```", "").strip()
                merge_groups = json.loads(content)
                for group in merge_groups:
                    if len(group) > 1:
                        primary = group[0]
                        for secondary in group[1:]:
                            if self.graph_db.has_node(primary) and self.graph_db.has_node(secondary):
                                # Merge secondary into primary
                                self.graph_db = nx.contracted_nodes(self.graph_db, primary, secondary, self_loops=False)
            except Exception as e:
                print(f"Skipping entity resolution batch due to parse error.")

    def _build_and_summarize_communities(self):
        """Groups the graph into communities and generates summaries for ChromaDB."""
        if len(self.graph_db.nodes()) == 0: return
        
        # 1. Detect communities using Louvain algorithm
        communities = louvain_communities(self.graph_db)
        
        summaries = []
        metadatas = []
        
        # 2. Generate a summary for each community
        for i, community_nodes in enumerate(communities):
            subgraph = self.graph_db.subgraph(community_nodes)
            
            # Compile raw context for the LLM
            raw_context = []
            for node, data in subgraph.nodes(data=True):
                raw_context.append(f"Entity: {node} ({data.get('type', '')}) - {data.get('description', '')}")
            for u, v, data in subgraph.edges(data=True):
                raw_context.append(f"Relation: {u} -> {v} ({data.get('keywords', '')}) - {data.get('description', '')}")
                
            summary_prompt = f"Summarize the following related entities and their relationships into a cohesive, highly detailed overview:\n{chr(10).join(raw_context)}"
            response = self.llm.invoke(summary_prompt)
            summary = response.content if hasattr(response, "content") else str(response)
            
            summaries.append(summary)
            metadatas.append({"type": "community_summary", "community_id": str(i)})
            
        # 3. Embed the SUMMARIES into ChromaDB
        if summaries:
            self.vector_db.add_texts(texts=summaries, metadatas=metadatas)

    # ==========================================
    # PHASE 2: DUAL-LEVEL RETRIEVAL & GENERATION
    # ==========================================
    def retrieve(self, query: str) -> str:
        keywords = self._extract_query_keywords(query)
        all_keys = keywords.get("low_level_keywords", []) + keywords.get("high_level_keywords", [])
        
        retrieved_summaries = set()
        for key in all_keys:
            # We search ChromaDB for the embedded community summaries
            docs = self.vector_db.similarity_search(key, k=2)
            for d in docs:
                retrieved_summaries.add(d.page_content)
                
        return "\n---\n".join(list(retrieved_summaries))

    def _extract_query_keywords(self, query: str) -> dict:
        prompt = f"""
        Identify high-level (broad themes) and low-level (specific entities) keywords in the query.
        Output ONLY strict JSON with exactly two keys: "high_level_keywords" and "low_level_keywords".
        Query: {query}
        Output:
        """
        response = self.llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        try:
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except json.JSONDecodeError:
            return {"high_level_keywords": [query], "low_level_keywords": []}

    def generate(self, query: str) -> Dict[str, Any]:
        context = self.retrieve(query)
        
        prompt = f"""
        Based on the following retrieved knowledge graph summaries, answer the user's query directly and comprehensively. Show clear calculation steps if math is involved.
        
        Context:
        {context}
        
        Query: {query}
        Answer:"""
        
        response = self.llm.invoke(prompt)
        return {
            "answer": response.content if hasattr(response, "content") else str(response),
            "sources": ["Knowledge Graph Community Summaries"]
        }