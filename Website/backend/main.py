# backend/main.py
import os
from pathlib import Path

# ---- Fix OpenMP runtime conflicts on Windows (faiss/torch/etc) ----
# This prevents the libomp vs libiomp crash warning from killing performance or failing imports.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", os.getenv("OMP_NUM_THREADS", "1"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env for LOCAL DEV only (Azure/ACA will use real env vars)
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

ENV = os.getenv("ENV", "").lower()
docs_url = None if ENV in ("prod", "production") else "/docs"
redoc_url = None if ENV in ("prod", "production") else "/redoc"

app = FastAPI(
    title="AURA Backend",
    version="0.1.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
)

# ---- CORS ----
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/health")
def health():
    return {"ok": True}

def include_router_safely(module_name: str, label: str):
    try:
        mod = __import__(module_name, fromlist=["router"])
        router = getattr(mod, "router", None)
        if router is None:
            raise RuntimeError(f"{module_name} has no attribute 'router'")
        app.include_router(router)
        print(f"✅ Loaded router: {label}")
    except Exception as e:
        print(f"⚠️ Router not loaded ({label}): {e}")

# ---- Routers ----
include_router_safely("database_api", "database_api")
include_router_safely("camera_api", "camera_api")
include_router_safely("detect_api", "detect_api")
include_router_safely("admin_auth_api", "admin_auth_api")
include_router_safely("logs_api", "logs_api")
include_router_safely("auth_me_api", "auth_me_api")
include_router_safely("student_auth_api", "student_auth_api")
include_router_safely("ta_auth_api", "ta_auth_api")
include_router_safely("ta_admin_api", "ta_admin_api")
include_router_safely("tts_api", "tts_api")
include_router_safely("stt_api", "stt_api")

# ---- Warmup Ollama on startup (reduces first-request delay) ----
@app.on_event("startup")
async def _warm_ollama():
    try:
        from lightrag_local import OllamaClient  # uses your existing client

        ollama_url = os.getenv("AURA_OLLAMA_URL", "http://127.0.0.1:11434")
        llm = os.getenv("AURA_LLM_MODEL", "llama3.2:3b")
        emb = os.getenv("AURA_EMBED_MODEL", "nomic-embed-text")

        client = OllamaClient(base_url=ollama_url, embed_model=emb, llm_model=llm)
        # Load embed model + llm model into memory
        await client.embed("warmup")
        await client.generate(prompt="Say 'ready'.", system="", timeout_s=float(os.getenv("AURA_OLLAMA_TIMEOUT_S", "180")))
        print("✅ Ollama warmup complete")
    except Exception as e:
        print(f"⚠️ Ollama warmup skipped: {e}")