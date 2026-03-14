"""
routers/games.py — Games, members, invites management.

POST   /api/games                              — create game (auth required)
GET    /api/games                              — list my games
GET    /api/games/{game_id}                    — get game details
PATCH  /api/games/{game_id}                    — update game (admin+)
DELETE /api/games/{game_id}                    — delete game (owner)

GET    /api/games/{game_id}/members            — list members (member+)
PATCH  /api/games/{game_id}/members/{user_id}  — change role (admin+)
DELETE /api/games/{game_id}/members/{user_id}  — kick member (admin+, or self-leave)

POST   /api/games/{game_id}/invites            — create invite (moderator+)
GET    /api/games/{game_id}/invites            — list invites (admin+)
DELETE /api/games/{game_id}/invites/{invite_id} — revoke invite (admin+)

GET    /api/invites/{token}                    — get invite info (public)
POST   /api/invites/{token}/accept             — accept invite (auth required)
"""

import secrets
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import Game, GameMember, GameInvite, User
from core.permissions import require_role, get_membership, _role_level

router = APIRouter(prefix="/api", tags=["games"])


# ── Schemas ─────────────────────────────────────────────────────────────────

class CreateGameRequest(BaseModel):
    name: str
    settings: Optional[dict] = None


class UpdateGameRequest(BaseModel):
    name: Optional[str] = None
    settings: Optional[dict] = None


class UpdateRoleRequest(BaseModel):
    role: str


class CreateInviteRequest(BaseModel):
    role: str = "player"
    expires_in_hours: Optional[int] = None  # None = no expiry


# ── Helpers ──────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")[:80]
    return slug or "game"


def _unique_slug(name: str, db: Session, exclude_id: Optional[int] = None) -> str:
    base = _slugify(name)
    slug = base
    i = 2
    while True:
        q = db.query(Game).filter(Game.slug == slug)
        if exclude_id:
            q = q.filter(Game.id != exclude_id)
        if not q.first():
            return slug
        slug = f"{base}-{i}"
        i += 1


def _game_dict(game: Game, member: Optional[GameMember] = None) -> dict:
    return {
        "id": game.id,
        "name": game.name,
        "slug": game.slug,
        "owner_id": game.owner_id,
        "created_at": game.created_at.isoformat(),
        "settings": game.settings,
        "role": member.role if member else None,
    }


def _member_dict(m: GameMember) -> dict:
    return {
        "user_id": m.user_id,
        "username": m.user.username if m.user else None,
        "role": m.role,
        "joined_at": m.joined_at.isoformat(),
    }


def _invite_dict(inv: GameInvite) -> dict:
    return {
        "id": inv.id,
        "token": inv.token,
        "role": inv.role,
        "created_by": inv.created_by,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "used_at": inv.used_at.isoformat() if inv.used_at else None,
    }


# ── Games CRUD ───────────────────────────────────────────────────────────────

@router.post("/games", status_code=201)
async def create_game(
    body: CreateGameRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Game name required")

    slug = _unique_slug(name, db)
    game = Game(name=name, slug=slug, owner_id=user.id, settings=body.settings)
    db.add(game)
    db.flush()  # get game.id

    # Creator becomes owner member
    member = GameMember(game_id=game.id, user_id=user.id, role="owner")
    db.add(member)
    db.commit()
    db.refresh(game)
    db.refresh(member)
    return _game_dict(game, member)


@router.get("/games")
async def list_games(
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(GameMember)
        .filter(GameMember.user_id == user.id)
        .all()
    )
    result = []
    for m in memberships:
        game = db.get(Game, m.game_id)
        if game:
            result.append(_game_dict(game, m))
    return result


@router.get("/games/{game_id}")
async def get_game(
    game_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = get_membership(game_id, user, db)
    game = db.get(Game, game_id)
    return _game_dict(game, member)


@router.patch("/games/{game_id}")
async def update_game(
    game_id: int,
    body: UpdateGameRequest,
    member: GameMember = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    game = db.get(Game, game_id)
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Game name cannot be empty")
        game.name = name
        game.slug = _unique_slug(name, db, exclude_id=game_id)
    if body.settings is not None:
        game.settings = body.settings
    db.commit()
    db.refresh(game)
    db.refresh(member)
    return _game_dict(game, member)


@router.delete("/games/{game_id}", status_code=204)
async def delete_game(
    game_id: int,
    _member: GameMember = Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    game = db.get(Game, game_id)
    db.delete(game)
    db.commit()


# ── Members ──────────────────────────────────────────────────────────────────

@router.get("/games/{game_id}/members")
async def list_members(
    game_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_membership(game_id, user, db)  # ensure is member
    members = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id)
        .all()
    )
    return [_member_dict(m) for m in members]


@router.patch("/games/{game_id}/members/{target_user_id}")
async def update_member_role(
    game_id: int,
    target_user_id: int,
    body: UpdateRoleRequest,
    actor: GameMember = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    new_role = body.role
    if new_role not in ("player", "moderator", "admin", "owner"):
        raise HTTPException(400, f"Invalid role: {new_role}")

    # Cannot promote someone to a role higher than your own
    if _role_level(new_role) >= _role_level(actor.role):
        raise HTTPException(403, "Cannot assign a role equal to or higher than your own")

    target = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id, GameMember.user_id == target_user_id)
        .first()
    )
    if not target:
        raise HTTPException(404, "Member not found")

    # Cannot demote someone with equal/higher role
    if _role_level(target.role) >= _role_level(actor.role):
        raise HTTPException(403, "Cannot change role of a member with equal or higher permissions")

    # Protect last owner
    if target.role == "owner" and new_role != "owner":
        owners = db.query(GameMember).filter(
            GameMember.game_id == game_id, GameMember.role == "owner"
        ).count()
        if owners <= 1:
            raise HTTPException(400, "Cannot remove the last owner")

    target.role = new_role
    db.commit()
    db.refresh(target)
    return _member_dict(target)


@router.delete("/games/{game_id}/members/{target_user_id}", status_code=204)
async def kick_or_leave(
    game_id: int,
    target_user_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor_member = get_membership(game_id, user, db)

    target = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id, GameMember.user_id == target_user_id)
        .first()
    )
    if not target:
        raise HTTPException(404, "Member not found")

    is_self = target_user_id == user.id

    if not is_self:
        # Kicking someone else requires admin+
        if _role_level(actor_member.role) < _role_level("admin"):
            raise HTTPException(403, "Requires at least 'admin' role to kick members")
        # Cannot kick equal/higher role
        if _role_level(target.role) >= _role_level(actor_member.role):
            raise HTTPException(403, "Cannot kick a member with equal or higher permissions")

    # Protect last owner
    if target.role == "owner":
        owners = db.query(GameMember).filter(
            GameMember.game_id == game_id, GameMember.role == "owner"
        ).count()
        if owners <= 1:
            raise HTTPException(400, "Cannot remove the last owner")

    db.delete(target)
    db.commit()


# ── Invites ──────────────────────────────────────────────────────────────────

@router.post("/games/{game_id}/invites", status_code=201)
async def create_invite(
    game_id: int,
    body: CreateInviteRequest,
    actor: GameMember = Depends(require_role("moderator")),
    db: Session = Depends(get_db),
):
    if body.role not in ("player", "moderator", "admin"):
        raise HTTPException(400, f"Invalid invite role: {body.role}")

    # Cannot invite to a role >= own role
    if _role_level(body.role) >= _role_level(actor.role):
        raise HTTPException(403, "Cannot create invite for a role equal to or higher than your own")

    expires_at = None
    if body.expires_in_hours is not None:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(hours=body.expires_in_hours)

    invite = GameInvite(
        game_id=game_id,
        token=secrets.token_urlsafe(24),
        created_by=actor.user_id,
        role=body.role,
        expires_at=expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return _invite_dict(invite)


@router.get("/games/{game_id}/invites")
async def list_invites(
    game_id: int,
    _actor: GameMember = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    invites = db.query(GameInvite).filter(GameInvite.game_id == game_id).all()
    return [_invite_dict(inv) for inv in invites]


@router.delete("/games/{game_id}/invites/{invite_id}", status_code=204)
async def revoke_invite(
    game_id: int,
    invite_id: int,
    _actor: GameMember = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    invite = db.query(GameInvite).filter(
        GameInvite.id == invite_id, GameInvite.game_id == game_id
    ).first()
    if not invite:
        raise HTTPException(404, "Invite not found")
    db.delete(invite)
    db.commit()


# ── Public invite acceptance ─────────────────────────────────────────────────

@router.get("/invites/{token}")
async def get_invite_info(token: str, db: Session = Depends(get_db)):
    invite = db.query(GameInvite).filter(GameInvite.token == token).first()
    if not invite:
        raise HTTPException(404, "Invite not found")

    now = datetime.now(timezone.utc)
    expired = invite.expires_at and invite.expires_at.replace(tzinfo=timezone.utc) < now

    game = db.get(Game, invite.game_id)
    return {
        "token": invite.token,
        "game_id": invite.game_id,
        "game_name": game.name if game else None,
        "role": invite.role,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "used": invite.used_at is not None,
        "expired": expired,
    }


@router.post("/invites/{token}/accept")
async def accept_invite(
    token: str,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invite = db.query(GameInvite).filter(GameInvite.token == token).first()
    if not invite:
        raise HTTPException(404, "Invite not found")

    now = datetime.now(timezone.utc)
    if invite.used_at:
        raise HTTPException(409, "Invite already used")
    if invite.expires_at and invite.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(410, "Invite has expired")

    # Check not already a member
    existing = db.query(GameMember).filter(
        GameMember.game_id == invite.game_id, GameMember.user_id == user.id
    ).first()
    if existing:
        raise HTTPException(409, "Already a member of this game")

    member = GameMember(game_id=invite.game_id, user_id=user.id, role=invite.role)
    db.add(member)
    invite.used_at = now
    db.commit()
    db.refresh(member)

    game = db.get(Game, invite.game_id)
    return {"game_id": invite.game_id, "game_name": game.name if game else None, "role": member.role}
