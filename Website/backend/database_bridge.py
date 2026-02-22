import os
import shutil
import gc
from langchain_community.document_loaders import PyPDFLoader, TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_chroma import Chroma
from config import CHROMA_DIR, GRAPH_FILE, CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL, DEFAULT_MODEL
from lightrag import LightRAG

def ClearMemory():
    gc.collect()

def InitializeDatabase(docs_path: str, force_rebuild: bool = False):
    """Builds the Chroma Vector DB AND the NetworkX Graph DB using LightRAG indexing."""
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    
    if force_rebuild:
        if os.path.exists(CHROMA_DIR): shutil.rmtree(CHROMA_DIR)
        if os.path.exists(GRAPH_FILE): os.remove(GRAPH_FILE)
        
    if not os.path.exists(CHROMA_DIR) or not os.path.exists(GRAPH_FILE):
        os.makedirs(CHROMA_DIR, exist_ok=True)
        
        # 1. Load Docs
        loaders = {
            ".pdf": DirectoryLoader(docs_path, glob="**/*.pdf", loader_cls=PyPDFLoader),
            ".txt": DirectoryLoader(docs_path, glob="**/*.txt", loader_cls=TextLoader),
        }
        
        docs = []
        for ext, loader in loaders.items():
            try:
                loaded = loader.load()
                if loaded: docs.extend(loaded)
            except Exception as e:
                print(f"Error loading {ext}: {e}")
        
        if not docs:
            return None

        # 2. Chunk Docs
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks = splitter.split_documents(docs)
        
        # 3. Initialize blank DBs and pass to LightRAG for indexing
        vector_db = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
        llm = ChatOllama(model=DEFAULT_MODEL, temperature=0.1) # LLM needed for extraction
        
        rag_system = LightRAG(llm=llm, vector_db=vector_db, graph_file_path=GRAPH_FILE)
        
        # 4. Trigger the LightRAG Graph Extraction & Vectorization Pipeline
        rag_system.build_index(chunks)
        return vector_db
    
    return Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

def LoadDatabase():
    """Loads the existing Vector DB. (Graph is loaded inside LightRAG class init)"""
    if not os.path.exists(CHROMA_DIR) or not os.listdir(CHROMA_DIR):
        return None
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    return Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)