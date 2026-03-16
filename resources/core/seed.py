"""
core/seed.py — Сидирование базовой игры «Готика» при первом запуске.

Создаёт:
  - системного пользователя (system@ttrpg.local) — владелец базовой игры
  - игру «Готика» (slug: gothic) с 5 подключёнными движками
  - запись участника (owner) для системного пользователя

Идемпотентно: если игра уже существует — ничего не делает.
"""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import Game, GameEngine, GameMember, User

_SYSTEM_EMAIL = "system@ttrpg.local"
_SYSTEM_USERNAME = "Gothic Master"
_GOTHIC_SLUG = "gothic"

# Движки в порядке отображения (engine_id, order)
_GOTHIC_ENGINES: list[tuple[str, int]] = [
    ("profession_roll",  1),
    ("chest_game",       2),
    ("item_generator",   3),
    ("trader_inventory", 4),
    ("story_motivation", 5),
    ("treasure",         6),
]


def _get_or_create_system_user(db: Session) -> User:
    user = db.execute(
        select(User).where(User.email == _SYSTEM_EMAIL)
    ).scalar_one_or_none()

    if not user:
        # Генерируем случайный нерабочий хэш пароля — логин под этим аккаунтом невозможен
        fake_hash = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
        user = User(
            email=_SYSTEM_EMAIL,
            username=_SYSTEM_USERNAME,
            password_hash=fake_hash,
        )
        db.add(user)
        db.flush()

    return user


def seed_gothic_game(db: Session) -> Game | None:
    """Создаёт игру «Готика» с движками. Возвращает объект игры или None если уже есть."""
    existing = db.execute(
        select(Game).where(Game.slug == _GOTHIC_SLUG)
    ).scalar_one_or_none()

    if existing:
        return None

    system_user = _get_or_create_system_user(db)

    game = Game(
        name="Готика",
        slug=_GOTHIC_SLUG,
        owner_id=system_user.id,
        settings={},
    )
    db.add(game)
    db.flush()

    for engine_id, order in _GOTHIC_ENGINES:
        db.add(GameEngine(
            game_id=game.id,
            engine_id=engine_id,
            order=order,
        ))

    db.add(GameMember(
        game_id=game.id,
        user_id=system_user.id,
        role="owner",
    ))

    db.commit()
    return game


def run_seed() -> None:
    """Точка входа: запускать при старте приложения."""
    db = SessionLocal()
    try:
        game = seed_gothic_game(db)
        if game:
            print(f"[seed] Создана игра «{game.name}» (id={game.id}, slug={game.slug})")
        else:
            pass  # игра уже существует — тихо пропускаем
    except Exception as exc:
        print(f"[seed] Ошибка: {exc}")
        db.rollback()
    finally:
        db.close()
