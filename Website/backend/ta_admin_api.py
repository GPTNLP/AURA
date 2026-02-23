from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from security import require_auth
from aura_db import init_db, ta_list, ta_add, ta_remove

router = APIRouter(prefix="/admin/ta", tags=["ta-admin"])
init_db()

def _require_admin(request: Request):
    payload = require_auth(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload

def _is_tamu(email: str) -> bool:
    return (email or "").strip().lower().endswith("@tamu.edu")

class TaEmailReq(BaseModel):
    email: str

@router.get("/list")
def list_tas(request: Request):
    _require_admin(request)
    return {"ok": True, "items": ta_list()}

@router.post("/add")
def add_ta(req: TaEmailReq, request: Request):
    payload = _require_admin(request)
    email = (req.email or "").strip().lower()

    if not _is_tamu(email):
        raise HTTPException(status_code=400, detail="TA email must end with @tamu.edu")

    ta_add(email=email, added_by=payload.get("sub") or "admin")
    return {"ok": True}

@router.post("/remove")
def remove_ta(req: TaEmailReq, request: Request):
    _require_admin(request)
    email = (req.email or "").strip().lower()
    ta_remove(email=email)
    return {"ok": True}