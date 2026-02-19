import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env from Website/.env (one directory above /backend)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="ARUA Backend", version="0.1.0")

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

@app.get("/health")
def health():
    return {"ok": True}

# ---- Routers ----
# IMPORTANT: These filenames MUST match your backend folder filenames.

from camera_api import router as camera_router
app.include_router(camera_router)

# If your admin auth router is in admin_api.py (or auth_api.py), import accordingly:
try:
    from admin_api import router as admin_router
    app.include_router(admin_router)
except Exception as e:
    print("admin_api router not loaded:", e)

try:
    from auth_api import router as auth_router
    app.include_router(auth_router)
except Exception as e:
    print("auth_api router not loaded:", e)
