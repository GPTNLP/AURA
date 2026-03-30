import os
import json
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from security import require_auth

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

router = APIRouter(prefix="/logs", tags=["logs"])

LOG_DIR = Path(os.getenv("LOG_DIR", str(Path(__file__).resolve().parent / "storage")))
LOG_FILE = LOG_DIR / "chat_logs.jsonl"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_INGEST_SECRET = os.getenv("LOG_INGEST_SECRET", "")


def require_admin(request: Request) -> Dict[str, Any]:
    payload = require_auth(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload


def _append_log(obj: Dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _read_all_logs() -> List[Dict[str, Any]]:
    if not LOG_FILE.exists():
        return []

    out: List[Dict[str, Any]] = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
    return out


def _public_item(it: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "log_id": it.get("log_id"),
        "ts": it.get("ts"),
        "event": it.get("event"),
        "user_email": it.get("user_email"),
        "user_role": it.get("user_role"),
        "prompt": it.get("prompt"),
        "response_preview": it.get("response_preview"),
        "model": it.get("model"),
        "latency_ms": it.get("latency_ms"),
        "meta": it.get("meta", {}) or {},
        "source": it.get("source"),
    }


class LogWrite(BaseModel):
    event: str = "chat"
    prompt: Optional[str] = None
    response_preview: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


class LogIngest(BaseModel):
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
    Email/role are ALWAYS taken from token.
    """
    payload = require_auth(request)
    now = int(time.time())

    obj = {
        "log_id": uuid.uuid4().hex,
        "ts": now,
        "event": data.event,
        "user_email": payload.get("sub"),
        "user_role": payload.get("role"),
        "prompt": data.prompt,
        "response_preview": data.response_preview,
        "model": data.model,
        "latency_ms": data.latency_ms,
        "meta": data.meta or {},
        "source": "frontend_or_api",
    }
    _append_log(obj)
    return {"ok": True, "log_id": obj["log_id"]}


@router.post("/ingest")
def ingest_log(data: LogIngest, request: Request):
    """
    Server-to-server ingestion for ML/backend.
    Send header: X-LOG-SECRET: <LOG_INGEST_SECRET>
    """
    if not LOG_INGEST_SECRET:
        raise HTTPException(status_code=500, detail="Server missing LOG_INGEST_SECRET")

    secret = request.headers.get("x-log-secret", "")
    if not secret or secret != LOG_INGEST_SECRET:
        raise HTTPException(status_code=403, detail="Bad ingest secret")

    now = int(time.time())
    obj = {
        "log_id": uuid.uuid4().hex,
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
    return {"ok": True, "log_id": obj["log_id"]}


@router.get("/mine")
def my_logs(request: Request, limit: int = 200, offset: int = 0):
    """
    Any authed user can read THEIR OWN logs only.
    """
    payload = require_auth(request)
    me = (payload.get("sub") or "").strip().lower()

    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    items = _read_all_logs()
    items.reverse()

    mine = [it for it in items if str(it.get("user_email", "")).strip().lower() == me]
    page = mine[offset : offset + limit]

    return {
        "ok": True,
        "email": me,
        "total": len(mine),
        "limit": limit,
        "offset": offset,
        "items": [_public_item(it) for it in page],
    }


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

    items = _read_all_logs()
    items.reverse()

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
                    str(it.get("log_id", "")),
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
        "items": [_public_item(it) for it in page],
    }


@router.get("/get")
def get_log(request: Request, log_id: str):
    """
    Admin can fetch one full log entry by log_id.
    """
    require_admin(request)

    items = _read_all_logs()
    for it in reversed(items):
        if str(it.get("log_id") or "") == str(log_id):
            return {"ok": True, "item": it}

    raise HTTPException(status_code=404, detail="Log not found")