"""
core/permissions.py — Role-based access control for games.

Roles (ascending permissions):
  player     → can use engines, view results
  moderator  → + manage content (JSON), reset caches
  admin      → + manage members, engine configs, logs
  owner      → full control, including delete game
"""

from typing import Callable
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import GameMember, Game

ROLE_HIERARCHY: dict[str, int] = {
    "player": 1,
    "moderator": 2,
    "admin": 3,
    "owner": 4,
}


def role_level(role: str) -> int:
    return ROLE_HIERARCHY.get(role, 0)


# Keep private alias for internal use within this module
_role_level = role_level


def get_membership(game_id: int, user: AuthUser, db: Session) -> GameMember:
    """Return the GameMember record or raise 403/404."""
    game = db.get(Game, game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    member = (
        db.query(GameMember)
        .filter(GameMember.game_id == game_id, GameMember.user_id == user.id)
        .first()
    )
    if not member:
        raise HTTPException(403, "You are not a member of this game")
    return member


def require_role(min_role: str) -> Callable:
    """
    Dependency factory. Returns a FastAPI dependency that validates
    the current user has at least `min_role` in the game.

    Usage:
        @router.delete("/{game_id}")
        async def delete_game(
            game_id: int,
            _: GameMember = Depends(require_role("owner")),
        ): ...
    """
    def dependency(
        game_id: int,
        user: AuthUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> GameMember:
        member = get_membership(game_id, user, db)
        if _role_level(member.role) < _role_level(min_role):
            raise HTTPException(403, f"Requires at least '{min_role}' role")
        return member

    return dependency
