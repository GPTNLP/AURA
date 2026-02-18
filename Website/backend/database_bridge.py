"""
Bridge for database operations. 
"""

import os
import json
import gc
import shutil
from typing import List, Dict, Any, Optional
from uuid import uuid4
from datetime import datetime

import torch
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_SIZE, CHUNK_OVERLAP, CHROMA_DIR, STORAGE_DIR, SESSIONS_DIR

SPLITTER = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

def ClearCudaCache():
    """Aggressively clear memory."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    gc.collect()

def LoadDocuments(path: str) -> List[Document]:
    """Load documents from the staging directory."""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
        return []
    
    # Only using PDF and TXT for reliability
    loaders = {
        ".pdf": DirectoryLoader(path, glob="**/*.pdf", loader_cls=PyPDFLoader),
        ".txt": DirectoryLoader(path, glob="**/*.txt", loader_cls=TextLoader),
    }

    docs = []
    for file_type, loader in loaders.items():
        try:
            loaded = loader.load()
            if loaded:
                docs.extend(loaded)
                print(f"Loaded {len(loaded)} {file_type} files")
        except Exception as e:
            print(f"Warning: Could not load {file_type} files: {e}")
    
    return docs

def InitializeDatabase(embedding_model: str, docs_path: str, force_reload: bool = False) -> Chroma:
    """
    Initialize or rebuild the Chroma vector database.
    """
    os.makedirs(STORAGE_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    embeddings = OllamaEmbeddings(model=embedding_model)
    db_exists = os.path.isdir(CHROMA_DIR) and len(os.listdir(CHROMA_DIR)) > 0

    if force_reload:
        print("Force reload: Rebuilding database...")
        # Clear existing
        if os.path.exists(CHROMA_DIR):
            shutil.rmtree(CHROMA_DIR)
            os.makedirs(CHROMA_DIR)

        raw_docs = LoadDocuments(docs_path)
        if not raw_docs:
            # Return empty DB if no docs, to prevent crash
            print("No documents found to index.")
            return Chroma(embedding_function=embeddings, persist_directory=CHROMA_DIR)

        chunks = SPLITTER.split_documents(raw_docs)
        print(f"Generating embeddings for {len(chunks)} chunks...")
        
        db = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=CHROMA_DIR
        )
        print("Database built.")
        return db

    # Load existing
    print(f"Loading existing database from {CHROMA_DIR}")
    return Chroma(embedding_function=embeddings, persist_directory=CHROMA_DIR)

def ZipDatabase() -> str:
    """Zips the chroma directory for export."""
    shutil.make_archive("chroma_db", 'zip', CHROMA_DIR)
    return "chroma_db.zip"

def SaveSession(session_data: Dict[str, Any], session_id: Optional[str] = None) -> str:
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    if session_id is None:
        session_id = str(uuid4())
    
    session_data['timestamp'] = datetime.now().isoformat()
    session_data['session_id'] = session_id
    
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(filepath, 'w') as f:
        json.dump(session_data, f, indent=2)
    return session_id

def ListSessions() -> List[str]:
    if not os.path.exists(SESSIONS_DIR):
        return []
    return sorted([f[:-5] for f in os.listdir(SESSIONS_DIR) if f.endswith('.json')])

def LoadSession(session_id: str) -> Dict[str, Any]:
    filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r') as f:
        return json.load(f)