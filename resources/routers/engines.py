"""
routers/engines.py — Engine discovery, copy, config schema, and game-engine management.

GET    /api/engines                                    — list all registered engines (auth)
GET    /api/engines/primitives                         — list primitive mechanic types
POST   /api/engines/{engine_id}/copy                   — copy system engine to user registry
GET    /api/engines/{engine_id}/config-schema           — config schema for visual editor

GET    /api/games/{game_id}/engines                    — game's active engines (member+)
POST   /api/games/{game_id}/engines                    — add engine to game (admin+)
PATCH  /api/games/{game_id}/engines/{record_id}        — update order (admin+)
DELETE /api/games/{game_id}/engines/{record_id}        — remove engine (admin+)

POST   /api/games/{game_id}/engines/{engine_id}/action        — system engine action (player+)
POST   /api/games/{game_id}/user-engines/{record_id}/action   — user engine action (player+)
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import GameEngine, UserEngine
from core.permissions import require_role, get_membership
from engines import registry
from engines.composite import PRIMITIVE_MECHANICS

router = APIRouter(prefix="/api", tags=["engines"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class AddEngineRequest(BaseModel):
    engine_id: Optional[str] = None
    user_engine_id: Optional[int] = None
    order: int = 0


class UpdateEngineOrderRequest(BaseModel):
    order: int


class EngineActionRequest(BaseModel):
    action: str
    payload: dict = {}


class CopyEngineRequest(BaseModel):
    new_name: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _record_dict(rec: GameEngine) -> dict:
    return {
        "id": rec.id,
        "game_id": rec.game_id,
        "engine_id": rec.engine_id,
        "user_engine_id": rec.user_engine_id,
        "order": rec.order,
    }


def _resolve_engine_and_config(rec: GameEngine, db: Session) -> tuple:
    """
    Return (engine_instance, merged_config) for a GameEngine record.
    - System engine: engine from registry + default config
    - User engine (copy-mode): base system engine + custom_config
    - User engine (composite): CompositeEngine + mechanics
    """
    if rec.engine_id:
        engine = registry.get_engine(rec.engine_id)
        if not engine:
            raise HTTPException(404, f"Engine '{rec.engine_id}' not in registry")
        return engine, engine.get_default_config()

    # User engine
    user_eng: Optional[UserEngine] = db.get(UserEngine, rec.user_engine_id)
    if not user_eng:
        raise HTTPException(404, "User engine not found")

    if user_eng.base_engine_id:
        # Copy-mode: delegate to base system engine with custom config
        engine = registry.get_engine(user_eng.base_engine_id)
        if not engine:
            raise HTTPException(500, f"Base engine '{user_eng.base_engine_id}' not in registry")
        base_config = engine.get_default_config()
        base_config.update(user_eng.custom_config or {})
        return engine, base_config
    else:
        # Composite mode
        composite = registry.get_engine("composite")
        if not composite:
            raise HTTPException(500, "CompositeEngine not registered")
        return composite, {"mechanics": user_eng.mechanics or []}


def _get_disabled_actions(rec: GameEngine, db: Session) -> list:
    """Get disabled_actions for user engines (copy-mode only)."""
    if rec.user_engine_id:
        user_eng = db.get(UserEngine, rec.user_engine_id)
        if user_eng and user_eng.disabled_actions:
            return user_eng.disabled_actions
    return []


# ── Engine discovery ─────────────────────────────────────────────────────────

@router.get("/engines")
async def list_all_engines(_: AuthUser = Depends(get_current_user)):
    """List all registered system engine types with their metadata."""
    return [e for e in registry.list_engines() if e["engine_id"] != "composite"]


@router.get("/engines/primitives")
async def list_primitive_mechanics(_: AuthUser = Depends(get_current_user)):
    """List available primitive mechanic types for building custom engines."""
    return PRIMITIVE_MECHANICS


@router.post("/engines/{engine_id}/copy", status_code=201)
async def copy_system_engine(
    engine_id: str,
    body: CopyEngineRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Copy a system engine to user's engine registry."""
    engine = registry.get_engine(engine_id)
    if not engine or engine_id == "composite":
        raise HTTPException(404, f"System engine '{engine_id}' not found")

    name = body.new_name.strip() if body.new_name else f"{engine.name} (копия)"
    if not name:
        raise HTTPException(400, "Engine name cannot be empty")

    user_eng = UserEngine(
        name=name,
        description=engine.description,
        owner_id=user.id,
        is_public=False,
        mechanics=None,
        base_engine_id=engine_id,
        custom_config=engine.get_default_config(),
        source_engine_id=engine_id,
        disabled_actions=[],
    )
    db.add(user_eng)
    db.commit()
    db.refresh(user_eng)

    return {
        "id": user_eng.id,
        "name": user_eng.name,
        "description": user_eng.description,
        "owner_id": user_eng.owner_id,
        "is_public": user_eng.is_public,
        "base_engine_id": user_eng.base_engine_id,
        "custom_config": user_eng.custom_config,
        "source_engine_id": user_eng.source_engine_id,
        "disabled_actions": user_eng.disabled_actions,
        "mechanics": None,
        "created_at": user_eng.created_at.isoformat() if user_eng.created_at else None,
    }


@router.get("/engines/{engine_id}/config-schema")
async def get_engine_config_schema(
    engine_id: str,
    _: AuthUser = Depends(get_current_user),
):
    """Return config schema for visual editor."""
    engine = registry.get_engine(engine_id)
    if not engine or engine_id == "composite":
        raise HTTPException(404, f"System engine '{engine_id}' not found")
    return engine.get_config_schema()


# ── Game engine management ───────────────────────────────────────────────────

@router.get("/games/{game_id}/engines")
async def list_game_engines(
    game_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_membership(game_id, user, db)
    records = (
        db.query(GameEngine)
        .filter(GameEngine.game_id == game_id)
        .order_by(GameEngine.order)
        .all()
    )
    result = []
    for rec in records:
        d = _record_dict(rec)
        disabled = _get_disabled_actions(rec, db)

        if rec.engine_id:
            engine = registry.get_engine(rec.engine_id)
            meta = engine.get_meta() if engine else None
            if meta and disabled:
                meta["actions"] = [a for a in meta.get("actions", []) if a["id"] not in disabled]
            d["meta"] = meta
            d["effective_config"] = engine.get_default_config() if engine else {}
        elif rec.user_engine_id:
            user_eng = db.get(UserEngine, rec.user_engine_id)
            if user_eng:
                if user_eng.base_engine_id:
                    # Copy-mode
                    engine = registry.get_engine(user_eng.base_engine_id)
                    meta = engine.get_meta() if engine else {}
                    meta = dict(meta)
                    meta.update({
                        "engine_id": f"user:{rec.user_engine_id}",
                        "name": user_eng.name,
                        "description": user_eng.description or "",
                        "base_engine_id": user_eng.base_engine_id,
                    })
                    if disabled:
                        meta["actions"] = [a for a in meta.get("actions", []) if a["id"] not in disabled]
                    d["meta"] = meta
                    base_config = engine.get_default_config() if engine else {}
                    base_config.update(user_eng.custom_config or {})
                    d["effective_config"] = base_config
                else:
                    # Composite mode
                    composite = registry.get_engine("composite")
                    meta = composite.get_meta() if composite else {}
                    meta = dict(meta)
                    meta.update({
                        "engine_id": f"user:{rec.user_engine_id}",
                        "name": user_eng.name,
                        "description": user_eng.description or "",
                        "mechanics": user_eng.mechanics,
                    })
                    d["meta"] = meta
                    d["effective_config"] = {"mechanics": user_eng.mechanics or []}
            else:
                d["meta"] = None
                d["effective_config"] = {}
        result.append(d)
    return result


@router.post("/games/{game_id}/engines", status_code=201)
async def add_engine_to_game(
    game_id: int,
    body: AddEngineRequest,
    _actor=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if bool(body.engine_id) == bool(body.user_engine_id):
        raise HTTPException(400, "Provide exactly one of engine_id or user_engine_id")

    if body.engine_id:
        if not registry.get_engine(body.engine_id):
            raise HTTPException(404, f"Unknown engine: {body.engine_id}")
        existing = db.query(GameEngine).filter(
            GameEngine.game_id == game_id,
            GameEngine.engine_id == body.engine_id,
        ).first()
        if existing:
            raise HTTPException(409, f"Engine '{body.engine_id}' already in this game")
        rec = GameEngine(
            game_id=game_id,
            engine_id=body.engine_id,
            order=body.order,
        )
    else:
        user_eng = db.get(UserEngine, body.user_engine_id)
        if not user_eng:
            raise HTTPException(404, f"User engine {body.user_engine_id} not found")
        if not user_eng.is_public and user_eng.owner_id != _actor.user_id:
            raise HTTPException(403, "Cannot add a private engine you don't own")
        existing = db.query(GameEngine).filter(
            GameEngine.game_id == game_id,
            GameEngine.user_engine_id == body.user_engine_id,
        ).first()
        if existing:
            raise HTTPException(409, "This user engine is already in the game")
        rec = GameEngine(
            game_id=game_id,
            user_engine_id=body.user_engine_id,
            order=body.order,
        )

    db.add(rec)
    db.commit()
    db.refresh(rec)
    d = _record_dict(rec)
    if rec.engine_id:
        engine = registry.get_engine(rec.engine_id)
        d["meta"] = engine.get_meta() if engine else None
    return d


@router.patch("/games/{game_id}/engines/{record_id}")
async def update_game_engine(
    game_id: int,
    record_id: int,
    body: UpdateEngineOrderRequest,
    _actor=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    rec = db.query(GameEngine).filter(
        GameEngine.id == record_id, GameEngine.game_id == game_id
    ).first()
    if not rec:
        raise HTTPException(404, "Engine record not found")

    rec.order = body.order
    db.commit()
    db.refresh(rec)
    return _record_dict(rec)


@router.delete("/games/{game_id}/engines/{record_id}", status_code=204)
async def remove_game_engine(
    game_id: int,
    record_id: int,
    _actor=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    rec = db.query(GameEngine).filter(
        GameEngine.id == record_id, GameEngine.game_id == game_id
    ).first()
    if not rec:
        raise HTTPException(404, "Engine record not found")
    db.delete(rec)
    db.commit()


# ── Engine action execution ───────────────────────────────────────────────────

@router.post("/games/{game_id}/engines/{engine_id}/action")
async def execute_system_engine_action(
    game_id: int,
    engine_id: str,
    body: EngineActionRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute an action on a system (built-in) engine in this game."""
    get_membership(game_id, user, db)

    rec = db.query(GameEngine).filter(
        GameEngine.game_id == game_id,
        GameEngine.engine_id == engine_id,
    ).first()
    if not rec:
        raise HTTPException(404, f"Engine '{engine_id}' is not enabled for this game")

    engine, config = _resolve_engine_and_config(rec, db)
    return engine.handle_action(body.action, body.payload, config)


@router.post("/games/{game_id}/user-engines/{record_id}/action")
async def execute_user_engine_action(
    game_id: int,
    record_id: int,
    body: EngineActionRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Execute an action on a user-created engine in this game."""
    get_membership(game_id, user, db)

    rec = db.query(GameEngine).filter(
        GameEngine.id == record_id,
        GameEngine.game_id == game_id,
        GameEngine.user_engine_id.isnot(None),
    ).first()
    if not rec:
        raise HTTPException(404, f"User engine record {record_id} not found in this game")

    # Check disabled actions
    disabled = _get_disabled_actions(rec, db)
    if body.action in disabled:
        raise HTTPException(403, f"Action '{body.action}' is disabled for this engine")

    engine, config = _resolve_engine_and_config(rec, db)
    return engine.handle_action(body.action, body.payload, config)
