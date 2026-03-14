"""
core/log.py — DB-backed journal utilities.

Log entries store arbitrary engine result data in the `data` JSON column.
Pagination is ID-based (after_id) for stability.
"""

from typing import Optional
from sqlalchemy.orm import Session
from core.models import GameLog

LOG_PAGE_SIZE = 100


def append_entry(
    db: Session,
    game_id: int,
    data: dict,
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
    visibility: str = "public",
) -> GameLog:
    entry = GameLog(
        game_id=game_id,
        user_id=user_id,
        user_name=user_name,
        visibility=visibility,
        data=data,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_entries(
    db: Session,
    game_id: int,
    after_id: int = 0,
    is_admin: bool = False,
    limit: int = LOG_PAGE_SIZE,
) -> list[GameLog]:
    q = db.query(GameLog).filter(
        GameLog.game_id == game_id,
        GameLog.id > after_id,
    )
    if not is_admin:
        q = q.filter(GameLog.visibility == "public")
    return q.order_by(GameLog.id.asc()).limit(limit).all()


def clear_game_log(db: Session, game_id: int) -> None:
    db.query(GameLog).filter(GameLog.game_id == game_id).delete()
    db.commit()
