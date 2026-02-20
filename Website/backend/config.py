"""
Configuration file for the AURA project.
"""

import os

# -------------------------
# Paths (your existing)
# -------------------------
BASE_DIR = os.getcwd()
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
CHROMA_DIR = os.path.join(STORAGE_DIR, "chroma")
SESSIONS_DIR = os.path.join(STORAGE_DIR, "sessions")
DOCS_STAGING_DIR = os.path.join(BASE_DIR, "source_documents")

# -------------------------
# AI Settings (your existing)
# -------------------------
DEFAULT_MODEL = "llama3.2"  # 3B quantized
EMBEDDING_MODEL = "nomic-embed-text"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
LIGHTRAG_K = 6

# -------------------------
# Auth / Security Settings (NEW)
# -------------------------

# Optional allowlist of IPs (comma-separated). Leave empty to disable allowlist.
ALLOWED_IPS = {ip.strip() for ip in os.getenv("ALLOWED_IPS", "").split(",") if ip.strip()}

# Camera token for camera endpoints (if you use that)
API_TOKEN = os.getenv("API_TOKEN", "")

# Secret for signing auth tokens (required for admin/student auth to work)
AUTH_SECRET = os.getenv("AUTH_SECRET", "")

# Allowed email domains for student login (comma-separated).
# Default includes tamu.edu if you don't set anything.
AUTH_ALLOWED_DOMAINS = {
    d.strip().lower()
    for d in (os.getenv("AUTH_ALLOWED_DOMAINS", "tamu.edu")).split(",")
    if d.strip()
}