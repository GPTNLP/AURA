"""
File to handle connecting documents from database to LightRAG
system on-device. Will also log sessions to be remotely stored & accessed
later for feedback/record keeping.

Provides:
- CombineDocuments(docs) -> str
- PullDocuments(documentPath) -> List[Document]
- PushDocuments(model_name, documentPath, reload=False) -> Chroma
- SaveSession(session_data, session_id=None) -> str (outputs file name)
- PullSession(session_id=None) -> dict | list[dict]
- ListSessions() -> list[str]
"""

import os
import json
import subprocess
import gc
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader, UnstructuredWordDocumentLoader

from langchain_core.documents import Document
from langchain_core.prompts import format_document
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
import torch

from Fritzer_AI.config import DEFAULT_DOC_PROMPT, CHUNK_SIZE, CHUNK_OVERLAP, CHROMA_DIR, STORAGE_DIR, SESSIONS_DIR

SPLITTER = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

def ClearCudaCache():
    """Clear CUDA cache to free GPU memory"""
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            print("CUDA cache cleared")
    except ImportError:
        pass
    
    # Force garbage collection
    gc.collect()
    print("Garbage collection completed")

def CombineDocuments(docs: List[Document]) -> str:
    """Combine documents into single string for context"""
    formatted = [format_document(doc, DEFAULT_DOC_PROMPT) for doc in docs]
    return "\n\n".join(formatted)


def LoadDocuments(path: str) -> List[Document]:
    """Load documents from directory"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path does not exist: {path}")
    
    loaders = {
        ".pdf": DirectoryLoader(path, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True),
        ".txt": DirectoryLoader(path, glob="**/*.txt", loader_cls=TextLoader, show_progress=True),
        ".md": DirectoryLoader(path, glob="**/*.md", loader_cls=TextLoader, show_progress=True)
        # ".docx": DirectoryLoader(path, glob="**/*.docx", loader_cls=UnstructuredWordDocumentLoader, show_progress=True)
    }

    docs = []
    for file_type, loader in loaders.items():
        try:
            loaded = loader.load()
            docs.extend(loaded)
            if loaded:
                print(f"Loaded {len(loaded)} {file_type} files")
        except Exception as e:
            print(f"Warning: Could not load {file_type} files: {e}")

    if not docs:
        print(f"Warning: No documents found in {path}")
    
    return docs


def kill_ollama(model: str):
    """Stop the Ollama instance for the given model."""
    try:
        subprocess.run(["ollama", "stop", model], check=False)
        print(f"Ollama model '{model}' stopped.")
    except Exception as e:
        print(f"Warning: Failed to stop Ollama: {e}")

def InitializeDatabase(embedding_model: str, docs_path: str, force_reload: bool = False) -> Chroma:
    """Initialize or load the Chroma vector database, then shut down Ollama."""
    
    os.makedirs(STORAGE_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    db_exists = os.path.isdir(CHROMA_DIR) and len(os.listdir(CHROMA_DIR)) > 0

    # Always instantiate embeddings once
    embeddings = OllamaEmbeddings(model=embedding_model)

    def build_database():
        print("Building vector database from documents...")

        raw_docs = LoadDocuments(docs_path)
        if not raw_docs:
            raise ValueError(f"No documents found in {docs_path}")

        chunks = SPLITTER.split_documents(raw_docs)
        print(f"Created {len(chunks)} chunks")
        print("Generating embeddings...")

        db = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=CHROMA_DIR
        )
        print("Database created and saved")
        return db

    if force_reload:
        print("Force reload requested – rebuilding database.")
        db = build_database()
        kill_ollama(embedding_model)
        return db

    if db_exists:
        print(f"Loading existing database from {CHROMA_DIR}")
        try:
            db = Chroma(
                embedding_function=embeddings,
                persist_directory=CHROMA_DIR
            )
            print("Database loaded successfully")
            kill_ollama(embedding_model)
            return db
        except Exception as e:
            print(f"Error loading existing database: {e}")
            print("Falling back to rebuild...")

    db = build_database()
    kill_ollama(embedding_model)
    return db

def SaveSession(session_data: Dict[str, Any], session_id: Optional[str] = None) -> str:
    """Save chat session to file"""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    
    if session_id is None:
        session_id = str(uuid4())
    
    filename_id = session_id
    
    session_data['timestamp'] = datetime.now().isoformat()
    session_data['session_id'] = session_id
    
    filepath = os.path.join(SESSIONS_DIR, f"{filename_id}.json")
    
    # Write session (overwrites previous if exists)
    with open(filepath, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    print(f"Session saved: {filepath}")
    return filename_id


def LoadSession(session_id: str) -> Dict[str, Any]:
    """Load chat session from file"""
    filename = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Session {session_id} not found")
    
    with open(filename, 'r') as f:
        return json.load(f)


def ListSessions() -> List[str]:
    """List all saved session IDs"""
    if not os.path.exists(SESSIONS_DIR):
        return []
    
    sessions = []
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith('.json'):
            sessions.append(filename[:-5])
    
    return sorted(sessions)