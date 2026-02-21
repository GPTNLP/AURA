# Website/backend/logs_api.py
import os
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from security_tokens import verify_token

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

router = APIRouter(prefix="/logs", tags=["logs"])

LOG_DIR = Path(os.getenv("LOG_DIR", str(Path(__file__).resolve().parent / "storage")))
LOG_FILE = LOG_DIR / "chat_logs.jsonl"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Secret used by the ML backend to push logs (server-to-server)
LOG_INGEST_SECRET = os.getenv("LOG_INGEST_SECRET", "")


def _get_bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return auth.split(" ", 1)[1].strip()


def require_auth(request: Request) -> Dict[str, Any]:
    token = _get_bearer(request)
    try:
        return verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_admin(request: Request) -> Dict[str, Any]:
    payload = require_auth(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload


def _append_log(obj: Dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _read_logs(limit: int, offset: int) -> List[Dict[str, Any]]:
    if not LOG_FILE.exists():
        return []

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lines.reverse()  # newest first

    start = max(0, offset)
    end = max(0, offset + limit)

    out: List[Dict[str, Any]] = []
    for line in lines[start:end]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


class LogWrite(BaseModel):
    event: str = "chat"
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    prompt: Optional[str] = None
    response_preview: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


class LogIngest(BaseModel):
    """
    Same idea as LogWrite but intended for server-to-server (ML backend -> this backend)
    """
    event: str = "chat"
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    prompt: Optional[str] = None
    response_preview: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


@router.post("/write")
def write_log(data: LogWrite, request: Request):
    """
    Authenticated users can write a log entry.
    """
    payload = require_auth(request)
    now = int(time.time())

    obj = {
        "ts": now,
        "event": data.event,
        "user_email": data.user_email or payload.get("sub"),
        "user_role": data.user_role or payload.get("role"),
        "prompt": data.prompt,
        "response_preview": data.response_preview,
        "model": data.model,
        "latency_ms": data.latency_ms,
        "meta": data.meta or {},
        "source": "frontend_or_api",
    }
    _append_log(obj)
    return {"ok": True}


@router.post("/ingest")
def ingest_log(data: LogIngest, request: Request):
    """
    Server-to-server ingestion for ML backend.
    Send header: X-LOG-SECRET: <LOG_INGEST_SECRET>
    """
    if not LOG_INGEST_SECRET:
        raise HTTPException(status_code=500, detail="Server missing LOG_INGEST_SECRET")

    secret = request.headers.get("x-log-secret", "")
    if not secret or secret != LOG_INGEST_SECRET:
        raise HTTPException(status_code=403, detail="Bad ingest secret")

    now = int(time.time())
    obj = {
        "ts": now,
        "event": data.event,
        "user_email": data.user_email,
        "user_role": data.user_role,
        "prompt": data.prompt,
        "response_preview": data.response_preview,
        "model": data.model,
        "latency_ms": data.latency_ms,
        "meta": data.meta or {},
        "source": "ml_ingest",
    }
    _append_log(obj)
    return {"ok": True}


@router.get("/list")
def list_logs(
    request: Request,
    limit: int = 200,
    offset: int = 0,
    q: str = "",
    role: str = "",
    event: str = "",
):
    require_admin(request)

    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    items = _read_logs(limit=5000, offset=0)

    q_l = (q or "").strip().lower()
    role_l = (role or "").strip().lower()
    event_l = (event or "").strip().lower()

    def matches(it: Dict[str, Any]) -> bool:
        if event_l and str(it.get("event", "")).lower() != event_l:
            return False
        if role_l and str(it.get("user_role", "")).lower() != role_l:
            return False
        if q_l:
            blob = " ".join(
                [
                    str(it.get("user_email", "")),
                    str(it.get("user_role", "")),
                    str(it.get("event", "")),
                    str(it.get("prompt", "")),
                    str(it.get("response_preview", "")),
                    json.dumps(it.get("meta", {}), ensure_ascii=False),
                ]
            ).lower()
            if q_l not in blob:
                return False
        return True

    filtered = [it for it in items if matches(it)]
    page = filtered[offset : offset + limit]

    return {
        "ok": True,
        "total_scanned": len(items),
        "total_matched": len(filtered),
        "limit": limit,
        "offset": offset,
        "items": page,
    }