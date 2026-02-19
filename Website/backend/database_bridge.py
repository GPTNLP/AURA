"""
Bridge for database operations. 
"""

"""
Bridge for database operations using LightRAG indexing.
"""

import os
import shutil
import gc
import networkx as nx
from typing import List
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from config import CHROMA_DIR, CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL, DEFAULT_MODEL
from lightrag import LightRAG

def ClearMemory():
    """Force garbage collection."""
    gc.collect()

def InitializeDatabase(docs_path: str, force_rebuild: bool = False):
    """
    Builds the LightRAG Graph and ChromaDB from documents.
    Used primarily by the Admin Backend.
    """
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    llm = OllamaLLM(model=DEFAULT_MODEL)
    
    # Path to save the NetworkX graph alongside the Chroma SQLite files
    graph_path = os.path.join(CHROMA_DIR, "lightrag.graphml")
    
    if force_rebuild and os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
        
    if not os.path.exists(CHROMA_DIR):
        os.makedirs(CHROMA_DIR)
        
        # 1. Load Docs
        loaders = {
            ".pdf": DirectoryLoader(docs_path, glob="**/*.pdf", loader_cls=PyPDFLoader),
            ".txt": DirectoryLoader(docs_path, glob="**/*.txt", loader_cls=TextLoader),
        }
        
        docs = []
        for ext, loader in loaders.items():
            try:
                docs.extend(loader.load())
            except Exception as e:
                print(f"Error loading {ext}: {e}")
        
        if not docs:
            return None

        # 2. Split into Chunks
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks = splitter.split_documents(docs)
        
        # 3. Initialize Databases
        vector_db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
        rag_system = LightRAG(llm=llm, vector_db=vector_db)
        
        # 4. Build LightRAG Index (LLM Extraction + Graph Building + Vector Insertion)
        print(f"Starting LightRAG graph-based indexing on {len(chunks)} chunks...")
        print("NOTE: This will take a significant amount of time on edge hardware.")
        rag_system.build_index(chunks)
        
        # 5. Persist the Graph
        # We save this in CHROMA_DIR so the admin_api.py zip process captures it for deployment
        nx.write_graphml(rag_system.graph_db, graph_path)
        print("Graph and Vector Database built and saved successfully.")
        
        return rag_system
    
    # If not rebuilding, just load existing data
    vector_db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    rag_system = LightRAG(llm=llm, vector_db=vector_db)
    
    if os.path.exists(graph_path):
        rag_system.graph_db = nx.read_graphml(graph_path)
        
    return rag_system

def LoadDatabase():
    """
    Loads the existing LightRAG DB (Graph + Vector).
    Used by the Edge Nano Backend for querying.
    """
    if not os.path.exists(CHROMA_DIR) or not os.listdir(CHROMA_DIR):
        return None
        
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    llm = OllamaLLM(model=DEFAULT_MODEL)
    
    vector_db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    rag_system = LightRAG(llm=llm, vector_db=vector_db)
    
    graph_path = os.path.join(CHROMA_DIR, "lightrag.graphml")
    if os.path.exists(graph_path):
        rag_system.graph_db = nx.read_graphml(graph_path)
    else:
        print("Warning: Chroma DB found, but LightRAG graphml file is missing!")
        
    return rag_system