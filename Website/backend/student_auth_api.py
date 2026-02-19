from fastapi import APIRouter

router = APIRouter(prefix="/auth/student", tags=["student-auth"])

# Placeholder for now (we’ll replace with TAMU SSO later)
@router.get("/status")
def status():
    return {
        "ok": True,
        "mode": "placeholder",
        "next": "Implement TAMU SSO (OIDC/CAS/SAML) or student email OTP"
    }
