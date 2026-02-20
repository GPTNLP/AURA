import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env from Website/.env (one directory above /backend)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="AURA Backend", version="0.1.0")

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

# Camera API router (APIRouter)
from camera_api import router as camera_router
app.include_router(camera_router)

# Admin Auth API router (APIRouter) -> /auth/admin/login, /auth/admin/verify, /auth/admin/me
try:
    from admin_auth_api import router as admin_auth_router
    app.include_router(admin_auth_router)
except Exception as e:
    print("admin_auth_api router not loaded:", e)

# Student OTP router (APIRouter) -> /auth/student/start, /auth/student/verify
try:
    from student_auth_api import router as student_auth_router
    app.include_router(student_auth_router)
except Exception as e:
    print("student_auth_api router not loaded:", e)

# Optional: Admin tools API (this file uses app = FastAPI(), not APIRouter)
# Mount it under /admin-tools so it doesn't collide with other routes.
try:
    from admin_api import app as admin_tools_app
    app.mount("/admin-tools", admin_tools_app)
except Exception as e:
    print("admin_api (tools) app not loaded:", e)