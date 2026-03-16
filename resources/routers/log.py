"""
routers/log.py — Per-game journal endpoints.

GET    /api/games/{game_id}/log              — poll entries (member+)
POST   /api/games/{game_id}/log              — append entry (member+)
DELETE /api/games/{game_id}/log              — clear journal (admin+)
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import GameMember
from core.permissions import require_role, get_membership, role_level
from core import log as game_log

router = APIRouter(prefix="/api/games", tags=["log"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class LogEntryRequest(BaseModel):
    data: dict
    visibility: str = "public"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _entry_dict(e) -> dict:
    return {
        "id": e.id,
        "user": e.user_name,
        "visibility": e.visibility,
        "timestamp": e.created_at.isoformat(),
        **e.data,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{game_id}/log")
async def get_log(
    game_id: int,
    after_id: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = get_membership(game_id, user, db)
    is_admin = role_level(member.role) >= role_level("admin")
    entries = game_log.get_entries(db, game_id, after_id=after_id, is_admin=is_admin)
    last_id = entries[-1].id if entries else after_id
    return {
        "entries": [_entry_dict(e) for e in entries],
        "last_id": last_id,
    }


@router.post("/{game_id}/log", status_code=201)
async def post_log(
    game_id: int,
    body: LogEntryRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_membership(game_id, user, db)
    entry = game_log.append_entry(
        db,
        game_id=game_id,
        data=body.data,
        user_id=user.id,
        user_name=user.name,
        visibility=body.visibility,
    )
    return {"id": entry.id}


@router.delete("/{game_id}/log", status_code=204)
async def delete_log(
    game_id: int,
    _: GameMember = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    game_log.clear_game_log(db, game_id)
