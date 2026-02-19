"""
Configuration file for the AURA project.
"""

import os

# Paths
BASE_DIR = os.getcwd()
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
CHROMA_DIR = os.path.join(STORAGE_DIR, "chroma")
SESSIONS_DIR = os.path.join(STORAGE_DIR, "sessions")
DOCS_STAGING_DIR = os.path.join(BASE_DIR, "source_documents")

# AI Settings
DEFAULT_MODEL = "llama3.2"  # 3B quantized
EMBEDDING_MODEL = "nomic-embed-text"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
LIGHTRAG_K = 6