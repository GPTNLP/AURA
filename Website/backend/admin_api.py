import os
import shutil
import requests
import zipfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_ollama import ChatOllama
from lightrag import LightRAG
from config import DEFAULT_MODEL

# --- Paths & Constants ---
BASE_DIR = os.getcwd()
DOCS_STAGING_DIR = os.path.join(BASE_DIR, "source_documents")
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
CHROMA_DIR = os.path.join(STORAGE_DIR, "chroma")

# The internal IP of the Jetson Nano (e.g., Tailscale IP or University Static IP)
NANO_IP = "http://192.168.1.100:8000" 

app = FastAPI(title="AURA Admin API")

# Allow the frontend (React/Next.js) to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: You will need to drop your `database_bridge.py` into this backend folder 
# and import it here to handle the Chroma logic, as established in the previous step.
from database_bridge import InitializeDatabase, LoadDatabase

class ChatRequest(BaseModel):
    query: str

@app.post("/api/chat")
async def simulate_chat(request: ChatRequest):
    """Simulates the Jetson Nano chat experience locally on the Admin machine."""
    # 1. Load the locally compiled database
    db = LoadDatabase()
    if not db:
        raise HTTPException(status_code=404, detail="No local database found. Please build the database first.")
    
    try:
        # 2. Initialize the model (Ensure Ollama is running on your admin machine)
        llm = ChatOllama(model=DEFAULT_MODEL, temperature=0.05)
        rag_system = LightRAG(llm, db)
        
        # 3. Generate the response
        result = rag_system.generate(request.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_docs(files: list[UploadFile] = File(...)):
    if os.path.exists(DOCS_STAGING_DIR):
        shutil.rmtree(DOCS_STAGING_DIR)
    os.makedirs(DOCS_STAGING_DIR)
    
    for file in files:
        file_path = os.path.join(DOCS_STAGING_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
    return {"status": f"Uploaded {len(files)} files"}

@app.post("/api/build")
async def build_db():
    try:
        InitializeDatabase("nomic-embed-text", DOCS_STAGING_DIR, force_reload=True)
        return {"status": "Database built successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/deploy")
async def deploy_to_nano():
    zip_path = "storage_deploy"
    if not os.path.exists(CHROMA_DIR) or not os.path.exists(GRAPH_FILE):
        raise HTTPException(status_code=400, detail="Incomplete database to deploy")
    
    # Zip the entire STORAGE_DIR (which contains both chroma/ and the graphml file)
    # Exclude sessions to prevent overwriting Nano logs
    temp_deploy_dir = os.path.join(BASE_DIR, "temp_deploy")
    os.makedirs(temp_deploy_dir, exist_ok=True)
    shutil.copytree(CHROMA_DIR, os.path.join(temp_deploy_dir, "chroma"))
    shutil.copy2(GRAPH_FILE, temp_deploy_dir)
    
    shutil.make_archive(zip_path, 'zip', temp_deploy_dir)
    shutil.rmtree(temp_deploy_dir)
    
    try:
        with open(zip_path + ".zip", "rb") as f:
            response = requests.post(f"{NANO_IP}/api/sync-db", files={"file": f}, timeout=600)
        return {"status": "Deploy successful", "nano_response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to contact Nano: {str(e)}")

@app.get("/api/nano-status")
async def check_nano():
    try:
        # 2 second timeout to ensure the UI doesn't hang waiting for an offline robot
        resp = requests.get(f"{NANO_IP}/health", timeout=2)
        return {"online": True, "details": resp.json()}
    except:
        return {"online": False}

if __name__ == "__main__":
    import uvicorn
    # Runs the backend on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)