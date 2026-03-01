"""
Auth module — simple name-based authentication via cookie.

Currently stores just a display name with no password.
This module is self-contained: to replace with real auth (JWT, OAuth, etc.)
swap out the internals of get_current_user / router without touching the rest of the app.
"""

from urllib.parse import quote, unquote
from fastapi import APIRouter, HTTPException, Request, Response

COOKIE_NAME = "gotika_user"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


class AuthUser:
    def __init__(self, name: str):
        self.name = name


def get_current_user(request: Request) -> AuthUser:
    """Return AuthUser from cookie, or raise 401."""
    name = unquote(request.cookies.get(COOKIE_NAME, "")).strip()
    if not name:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return AuthUser(name)


def get_current_user_optional(request: Request) -> AuthUser | None:
    """Return AuthUser from cookie, or None if not authenticated."""
    name = unquote(request.cookies.get(COOKIE_NAME, "")).strip()
    return AuthUser(name) if name else None


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request, response: Response):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Name is required")
    if len(name) > 60:
        raise HTTPException(400, "Name is too long")
    response.set_cookie(
        key=COOKIE_NAME,
        value=quote(name),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return {"name": name}


@router.get("/me")
async def me(request: Request):
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return {"name": user.name}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}
