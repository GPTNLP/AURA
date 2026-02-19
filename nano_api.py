import os
import zipfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database_bridge import LoadDatabase
from config import CHROMA_DIR

app = FastAPI(title="AURA Edge API (Jetson Nano)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable to hold the loaded LightRAG system in RAM
rag_system = None

@app.on_event("startup")
async def startup_event():
    """Attempt to load an existing database on boot."""
    global rag_system
    try:
        rag_system = LoadDatabase()
        if rag_system:
            print("Successfully loaded existing LightRAG database on startup.")
    except Exception as e:
        print(f"Startup DB load skipped/failed. Waiting for deployment: {e}")

@app.get("/health")
async def health_check():
    """Allows the Admin panel to check if the Nano is online."""
    return {
        "status": "online",
        "database_loaded": rag_system is not None
    }

@app.post("/api/sync-db")
async def sync_database(file: UploadFile = File(...)):
    """Receives the deployed database zip, extracts it, and reloads the system."""
    global rag_system
    zip_path = "incoming_db.zip"
    
    # 1. Save the incoming zip file payload
    try:
        with open(zip_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save zip: {str(e)}")
        
    # 2. Extract the payload directly into the Chroma directory
    try:
        if not os.path.exists(CHROMA_DIR):
            os.makedirs(CHROMA_DIR)
            
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(CHROMA_DIR)
            
        # Clean up the zip file to save disk space
        os.remove(zip_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract DB: {str(e)}")
        
    # 3. Reload the LightRAG system into global memory
    try:
        rag_system = LoadDatabase()
        if not rag_system:
            raise Exception("LoadDatabase returned None")
        return {"status": "Database synced and loaded successfully"}
    except Exception as e:
        rag_system = None
        raise HTTPException(status_code=500, detail=f"Failed to load DB into memory: {str(e)}")

@app.post("/api/chat")
async def chat(query: str):
    """Answers user queries using the local LightRAG system."""
    if not rag_system:
        raise HTTPException(status_code=400, detail="Database not loaded. Please deploy from Admin first.")
        
    try:
        # Generate the RAG response
        response = rag_system.generate(query)
        return {
            "query": query,
            "answer": response["answer"],
            "context_used": response["context_used"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)