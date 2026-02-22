# backend/main.py
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env for LOCAL DEV only (Azure/ACA will use real env vars)
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Optional: hide docs in production
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
    # Local dev fallback
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

# ---- Routers ----
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

include_router_safely("camera_api", "camera_api")
include_router_safely("files_api", "files_api")
include_router_safely("admin_auth_api", "admin_auth_api")
include_router_safely("logs_api", "logs_api")
include_router_safely("admin_tools_api", "admin_tools_api")
include_router_safely("simulator_api", "simulator_api")