# Website/backend/main.py
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="AURA Backend", version="0.1.0")

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/health")
def health():
    return {"ok": True}

# ---- Routers ----
def try_include(import_path: str, name: str):
    try:
        mod = __import__(import_path, fromlist=["router"])
        app.include_router(mod.router)
        print(f"Loaded router: {name}")
    except Exception as e:
        print(f"Router not loaded ({name}): {e}")

try_include("camera_api", "camera_api")
try_include("files_api", "files_api")
try_include("admin_auth_api", "admin_auth_api")
try_include("student_auth_api", "student_auth_api")
try_include("logs_api", "logs_api")

# Optional: Admin tools API (FastAPI app)
try:
    from admin_api import app as admin_tools_app
    app.mount("/admin-tools", admin_tools_app)
    print("Mounted admin-tools app")
except Exception as e:
    print("admin_api (tools) app not loaded:", e)