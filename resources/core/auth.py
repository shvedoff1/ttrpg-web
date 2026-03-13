"""
core/auth.py — JWT utilities, password hashing, FastAPI dependencies.

Environment variables:
  SECRET_KEY           — HMAC secret for JWT signing (required in production)
  GOOGLE_CLIENT_ID     — Google OAuth2 client ID
  GOOGLE_CLIENT_SECRET — Google OAuth2 client secret
  GOOGLE_REDIRECT_URI  — e.g. https://yourdomain.com/auth/google/callback
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User

# ── Config ─────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30
REFRESH_COOKIE_NAME = "refresh_token"

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)

# ── Password hashing ───────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Token creation ─────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "username": username, "exp": expire, "type": "access"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "refresh"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── AuthUser ───────────────────────────────────────────────────────────────

class AuthUser:
    def __init__(self, id: int, username: str, email: Optional[str] = None):
        self.id = id
        self.username = username
        self.email = email

    @property
    def name(self) -> str:
        """Backward-compatible alias for username."""
        return self.username


# ── FastAPI dependencies ───────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: Optional[HTTPAuthorizationCredentials],
    request: Request,
) -> Optional[str]:
    """Try Authorization header first, then access_token cookie."""
    if credentials:
        return credentials.credentials
    return request.cookies.get("access_token")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    request: Request = None,
    db: Session = Depends(get_db),
) -> AuthUser:
    token = _extract_token(credentials, request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = _decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user: Optional[User] = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return AuthUser(id=user.id, username=user.username, email=user.email)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Optional[AuthUser]:
    token = _extract_token(credentials, request)
    if not token:
        return None
    try:
        payload = _decode_token(token)
        if payload.get("type") != "access":
            return None
        user: Optional[User] = db.get(User, int(payload["sub"]))
        if not user:
            return None
        return AuthUser(id=user.id, username=user.username, email=user.email)
    except HTTPException:
        return None
