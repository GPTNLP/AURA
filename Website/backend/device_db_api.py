# backend/device_db_api.py
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel

from security import require_auth, require_ip_allowlist

router = APIRouter(tags=["device-db"])

DEVICE_SHARED_SECRET = (os.getenv("DEVICE_SHARED_SECRET", "") or "").strip()
STORAGE_DIR = Path(os.getenv("AURA_STORAGE_DIR", "storage"))
DEVICE_STATE_DIR = STORAGE_DIR / "devices"
DEVICE_STATE_DIR.mkdir(parents=True, exist_ok=True)


def _role(payload: Dict[str, Any]) -> str:
    return str(payload.get("role") or "").lower()


def require_any_user(request: Request) -> Dict[str, Any]:
    require_ip_allowlist(request)
    return require_auth(request)


def require_admin_or_ta(request: Request) -> Dict[str, Any]:
    payload = require_any_user(request)
    if _role(payload) not in ("admin", "ta"):
        raise HTTPException(status_code=403, detail="Admin/TA only")
    return payload


def require_device_secret(x_device_secret: Optional[str]):
    expected = DEVICE_SHARED_SECRET
    got = (x_device_secret or "").strip()

    if not expected:
        raise HTTPException(status_code=500, detail="DEVICE_SHARED_SECRET is not configured on backend")

    if got != expected:
        raise HTTPException(status_code=403, detail="Invalid device secret")


def _device_file(device_id: str) -> Path:
    safe = "".join(c for c in device_id if c.isalnum() or c in ("-", "_"))
    if not safe:
        raise HTTPException(status_code=400, detail="Invalid device_id")
    return DEVICE_STATE_DIR / f"{safe}.json"


def _read_device_state(device_id: str) -> Dict[str, Any]:
    path = _device_file(device_id)
    if not path.exists():
        return {
            "device_id": device_id,
            "selected_db": None,
            "updated_ts": int(time.time()),
        }

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "device_id": device_id,
            "selected_db": None,
            "updated_ts": int(time.time()),
        }


def _write_device_state(device_id: str, data: Dict[str, Any]):
    path = _device_file(device_id)
    data["device_id"] = device_id
    data["updated_ts"] = int(time.time())
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class SetSelectedDBRequest(BaseModel):
    selected_db: str


@router.get("/api/devices/{device_id}/selected_db")
def get_selected_db(device_id: str, request: Request):
    require_admin_or_ta(request)
    state = _read_device_state(device_id)
    return {
        "ok": True,
        "device_id": device_id,
        "selected_db": state.get("selected_db"),
        "updated_ts": state.get("updated_ts"),
    }


@router.post("/api/devices/{device_id}/selected_db")
def set_selected_db(device_id: str, req: SetSelectedDBRequest, request: Request):
    require_admin_or_ta(request)

    db_name = (req.selected_db or "").strip()
    if not db_name:
        raise HTTPException(status_code=400, detail="selected_db is required")

    state = _read_device_state(device_id)
    state["selected_db"] = db_name
    _write_device_state(device_id, state)

    return {
        "ok": True,
        "device_id": device_id,
        "selected_db": db_name,
        "updated_ts": state.get("updated_ts"),
    }


@router.get("/device/db_selection")
def device_get_db_selection(
    device_id: str,
    x_device_secret: Optional[str] = Header(default=None, alias="X-Device-Secret"),
):
    require_device_secret(x_device_secret)
    state = _read_device_state(device_id)
    return {
        "ok": True,
        "device_id": device_id,
        "selected_db": state.get("selected_db"),
        "updated_ts": state.get("updated_ts"),
    }