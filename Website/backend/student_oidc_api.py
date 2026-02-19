import os
import secrets
from pathlib import Path
from typing import Optional

import httpx
from authlib.jose import jwt
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from security_tokens import mint_app_token

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OIDC_TENANT = os.getenv("OIDC_TENANT", "organizations")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "http://127.0.0.1:9000/auth/student/callback")
OIDC_FRONTEND_REDIRECT = os.getenv("OIDC_FRONTEND_REDIRECT", "http://localhost:5173/student-portal")
OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid profile email")

AUTHORITY = f"https://login.microsoftonline.com/{OIDC_TENANT}/v2.0"
DISCOVERY_URL = f"{AUTHORITY}/.well-known/openid-configuration"

router = APIRouter(prefix="/auth/student", tags=["student-auth"])

# store state in a short-lived cookie (simple dev-friendly approach)
STATE_COOKIE = "arua_oidc_state"


async def get_discovery() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(DISCOVERY_URL)
        r.raise_for_status()
        return r.json()


def pick_email(claims: dict) -> Optional[str]:
    # Entra commonly provides one of these:
    for k in ["email", "preferred_username", "upn", "unique_name"]:
        v = claims.get(k)
        if isinstance(v, str) and "@" in v:
            return v.lower().strip()
    return None


@router.get("/login")
async def student_login():
    if not OIDC_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Missing OIDC_CLIENT_ID")
    if not OIDC_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Missing OIDC_REDIRECT_URI")

    discovery = await get_discovery()
    auth_endpoint = discovery["authorization_endpoint"]

    state = secrets.token_urlsafe(24)

    # PKCE would be best; keeping it simple for now.
    params = {
        "client_id": OIDC_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": OIDC_REDIRECT_URI,
        "response_mode": "query",
        "scope": OIDC_SCOPES,
        "state": state,
    }

    url = httpx.URL(auth_endpoint).copy_add_params(params)

    resp = RedirectResponse(str(url), status_code=302)
    resp.set_cookie(STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax")
    return resp


@router.get("/callback")
async def student_callback(request: Request, code: str = "", state: str = ""):
    saved_state = request.cookies.get(STATE_COOKIE, "")

    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    if not state or not saved_state or state != saved_state:
        raise HTTPException(status_code=400, detail="Invalid state")

    if not OIDC_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Missing OIDC_CLIENT_SECRET")

    discovery = await get_discovery()
    token_endpoint = discovery["token_endpoint"]
    jwks_uri = discovery["jwks_uri"]
    issuer = discovery["issuer"]

    async with httpx.AsyncClient(timeout=15) as client:
        token_res = await client.post(
            token_endpoint,
            data={
                "client_id": OIDC_CLIENT_ID,
                "client_secret": OIDC_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OIDC_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_res.raise_for_status()
        tokens = token_res.json()

        id_token = tokens.get("id_token")
        if not id_token:
            raise HTTPException(status_code=400, detail="Missing id_token")

        jwks = (await client.get(jwks_uri)).json()

    # Verify ID token signature + issuer + audience
    try:
        claims = jwt.decode(
            id_token,
            jwks,
            claims_options={
                "iss": {"essential": True, "value": issuer},
                "aud": {"essential": True, "value": OIDC_CLIENT_ID},
            },
        )
        claims.validate()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid id_token: {e}")

    email = pick_email(claims)
    if not email:
        raise HTTPException(status_code=400, detail="No email claim returned by IdP")

    # Mint your app token (student role)
    session = mint_app_token(email=email, role="student")

    # Redirect back to frontend with token + email.
    # For production, prefer an HttpOnly cookie. This is fine for local dev.
    redirect_url = httpx.URL(OIDC_FRONTEND_REDIRECT).copy_add_params(
        {"token": session["token"], "email": email, "role": "student"}
    )

    resp = RedirectResponse(str(redirect_url), status_code=302)
    resp.delete_cookie(STATE_COOKIE)
    return resp
