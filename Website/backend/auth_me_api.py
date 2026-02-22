# backend/auth_me_api.py

from fastapi import APIRouter, Request
from security import require_auth

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def me(request: Request):
    payload = require_auth(request)

    return {
        "user": {
            "email": payload.get("sub"),
            "role": payload.get("role"),
        },
        "iat": payload.get("iat"),
        "exp": payload.get("exp"),
    }