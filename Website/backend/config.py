"""
Configuration file for the AURA project.
"""

############################
###  Formatting Prompts  ###
############################

LIGHTRAG_PROMPT = """Answer the question using the evidence provided below. 

Rules:
1. State facts directly without hedging ("The voltage is...")
2. For calculations, clearly show each step
3. If information is missing, state what is missing
4. Do NOT fabricate components or concepts not mentioned
5. Keep answers concise and accurate
6. Use plain text formatting for formulas (V = I*R)

Evidence:
{evidence}

Question: {question}

Direct answer:
"""

#####################################
###  Database & Storage Settings  ###
#####################################

# Chunking
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

# Retrieval
LIGHTRAG_K = 6

# Models
# Ensure these match your remote server (admin) and Jetson (user)
DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"

# LLM Parameters
LLM_TEMPERATURE = 0.05
LLM_TOP_P = 0.85
LLM_MAX_TOKENS = 512

# Paths
DEFAULT_DOCS_PATH = "source_documents" # Staging area for uploaded files
STORAGE_DIR = "storage"
CHROMA_DIR = "storage/chroma"
SESSIONS_DIR = "storage/sessions"