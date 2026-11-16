from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
import jwt

from ..database import get_db
from ..models import AdminUser
from ..rate_limiter import login_rate_limiter
from ..schemas import LoginRequest, TokenResponse, AdminResponse
from ..security import create_access_token, verify_password, decode_access_token

router = APIRouter(prefix="/api/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = login_rate_limiter.extract_client_ip(request)
    login_rate_limiter.check_rate_limit(client_ip)

    user = db.query(AdminUser).filter(AdminUser.email == payload.email.lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        login_rate_limiter.record_failure(client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    login_rate_limiter.record_success(client_ip)
    return TokenResponse(access_token=create_access_token(str(user.id)))

def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(AdminUser, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Admin account is inactive")
    return user

@router.get("/me", response_model=AdminResponse)
def me(current_admin: AdminUser = Depends(get_current_admin)):
    return current_admin
