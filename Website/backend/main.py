import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env for LOCAL DEV only
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

# -----------------------
# CORS
# -----------------------
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/health")
def health():
    return {"ok": True}


# -----------------------
# Router loader
# -----------------------
def include_router_safely(module_name: str, label: str):
    try:
        mod = __import__(module_name, fromlist=["router"])
        router = getattr(mod, "router", None)
        if router is None:
            raise RuntimeError(f"{module_name} has no 'router'")
        app.include_router(router)
        print(f"✅ Loaded router: {label}")
    except Exception as e:
        print(f"⚠️ Router not loaded ({label}): {e}")


include_router_safely("camera_api", "camera_api")
include_router_safely("files_api", "files_api")
include_router_safely("admin_auth_api", "admin_auth_api")
include_router_safely("student_auth_api", "student_auth_api")
include_router_safely("logs_api", "logs_api")
include_router_safely("auth_me_api", "auth_me_api")

# -----------------------
# Optional admin tools (disabled unless enabled)
# -----------------------
if os.getenv("ENABLE_ADMIN_TOOLS", "").lower() in ("1", "true", "yes"):
    try:
        from admin_api import app as admin_tools_app
        app.mount("/admin-tools", admin_tools_app)
        print("✅ Mounted admin-tools app")
    except Exception as e:
        print("⚠️ admin_api not loaded:", e)
else:
    print("ℹ️ admin-tools disabled")