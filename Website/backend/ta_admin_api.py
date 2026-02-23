from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from security import require_auth, require_ip_allowlist
from ta_store import list_ta_items, add_ta, remove_ta

router = APIRouter(prefix="/admin/ta", tags=["admin-ta"])

class TaReq(BaseModel):
    email: str

def _require_admin(request: Request):
    require_ip_allowlist(request)
    payload = require_auth(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return payload

@router.get("/list")
def ta_list(request: Request):
    _require_admin(request)
    return {"items": list_ta_items()}

@router.post("/add")
def ta_add(req: TaReq, request: Request):
    payload = _require_admin(request)
    email = (req.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")

    admin_email = (payload.get("sub") or "").strip().lower()
    add_ta(email, added_by=admin_email)
    return {"ok": True, "items": list_ta_items()}

@router.post("/remove")
def ta_remove(req: TaReq, request: Request):
    _require_admin(request)
    email = (req.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Invalid email")

    remove_ta(email)
    return {"ok": True, "items": list_ta_items()}