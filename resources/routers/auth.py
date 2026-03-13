"""
routers/auth.py — Authentication endpoints.

POST /auth/register          — register with username + password
POST /auth/login             — login with username/email + password
GET  /auth/google            — redirect to Google OAuth consent screen
GET  /auth/google/callback   — handle Google OAuth callback
POST /auth/refresh           — exchange refresh_token cookie for new access_token
POST /auth/logout            — clear refresh_token cookie
GET  /auth/me                — return current user info
"""

import os
import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.database import get_db
from core.models import User
from core.auth import (
    AuthUser,
    REFRESH_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_DAYS,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    get_current_user,
    _decode_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


# ── Schemas ────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: str   # accepts username or email
    password: str


# ── Helpers ────────────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
    )


def _token_response(user: User, response: Response) -> dict:
    access = create_access_token(user.id, user.username)
    refresh = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh)
    return {
        "access_token": access,
        "token_type": "bearer",
        "username": user.username,
        "user_id": user.id,
    }


# ── Register ───────────────────────────────────────────────────────────────

@router.post("/register")
async def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    username = body.username.strip()
    password = body.password

    if len(username) < 2 or len(username) > 60:
        raise HTTPException(400, "Username must be 2–60 characters")
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    email = body.email.strip().lower() if body.email else None

    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username or email already taken")

    return _token_response(user, response)


# ── Login ──────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    identifier = body.username.strip()

    # Try to find by username or email
    user: Optional[User] = (
        db.query(User).filter(User.username == identifier).first()
        or db.query(User).filter(User.email == identifier.lower()).first()
    )

    if not user or not user.password_hash:
        raise HTTPException(401, "Invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    return _token_response(user, response)


# ── Google OAuth ───────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth is not configured")

    state = secrets.token_urlsafe(16)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    redirect = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")
    # Store state in short-lived httpOnly cookie for CSRF protection
    redirect.set_cookie("oauth_state", state, max_age=300, httponly=True, samesite="lax")
    return redirect


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    expected_state = request.cookies.get("oauth_state")
    if not expected_state or state != expected_state:
        raise HTTPException(400, "Invalid OAuth state")
    response.delete_cookie("oauth_state")
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth is not configured")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(400, "Failed to exchange Google code for token")
        token_data = token_resp.json()

        # Fetch user info
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(400, "Failed to fetch Google user info")
        info = userinfo_resp.json()

    google_id: str = info["id"]
    email: str = info.get("email", "")
    name: str = info.get("name", email.split("@")[0])

    # Find or create user
    user: Optional[User] = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        # Try to link to existing account by email
        if email:
            user = db.query(User).filter(User.email == email.lower()).first()
        if user:
            user.google_id = google_id
            db.commit()
        else:
            # Create new user — ensure unique username
            base_username = name.replace(" ", "_")[:50]
            username = base_username
            suffix = 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base_username}_{suffix}"
                suffix += 1

            user = User(username=username, email=email.lower() if email else None, google_id=google_id)
            db.add(user)
            try:
                db.commit()
                db.refresh(user)
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, "Account conflict, please try again")

    tokens = _token_response(user, response)
    # Redirect to app with access_token in query (JS picks it up and stores in memory)
    return RedirectResponse(f"/?access_token={tokens['access_token']}")


# ── Refresh ────────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(401, "No refresh token")

    payload = _decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")

    user: Optional[User] = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(401, "User not found")

    return _token_response(user, response)


# ── Logout ─────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(REFRESH_COOKIE_NAME)
    return {"ok": True}


# ── Me ─────────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(user: AuthUser = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "email": user.email}
