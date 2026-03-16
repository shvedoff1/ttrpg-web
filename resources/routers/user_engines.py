"""
routers/user_engines.py — CRUD for user-created engines.

GET    /api/engines/custom              — list (mine + public ones)
POST   /api/engines/custom              — create composite user engine
GET    /api/engines/custom/{id}         — get one (owner or public)
PATCH  /api/engines/custom/{id}         — update (owner only)
DELETE /api/engines/custom/{id}         — delete (owner only)
POST   /api/engines/custom/{id}/simulate — test-run an action
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import UserEngine, GameEngine
from engines import registry
from engines.primitives.registry import get_primitive
from engines._helpers import validate_config_warnings

router = APIRouter(prefix="/api/engines/custom", tags=["user-engines"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class MechanicDef(BaseModel):
    type: str
    label: str
    action: Optional[str] = None
    config: Optional[dict] = None


class CreateUserEngineRequest(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False
    mechanics: list[MechanicDef] = []


class UpdateUserEngineRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    mechanics: Optional[list[MechanicDef]] = None
    custom_config: Optional[dict] = None
    disabled_actions: Optional[list[str]] = None


class SimulateRequest(BaseModel):
    action: Optional[str] = None
    mechanic_index: int = 0
    payload: dict = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _engine_dict(eng: UserEngine) -> dict:
    return {
        "id": eng.id,
        "name": eng.name,
        "description": eng.description,
        "owner_id": eng.owner_id,
        "is_public": eng.is_public,
        "mechanics": eng.mechanics or [],
        "base_engine_id": eng.base_engine_id,
        "custom_config": eng.custom_config,
        "source_engine_id": eng.source_engine_id,
        "disabled_actions": eng.disabled_actions or [],
        "created_at": eng.created_at.isoformat() if eng.created_at else None,
    }


def _collect_mechanic_warnings(mechanics: list[dict]) -> list[str]:
    warnings = []
    for m in mechanics:
        warnings.extend(validate_config_warnings(m.get("type", ""), m.get("config")))
    return warnings


def _get_owned(engine_id: int, user: AuthUser, db: Session) -> UserEngine:
    eng = db.get(UserEngine, engine_id)
    if not eng:
        raise HTTPException(404, "User engine not found")
    if eng.owner_id != user.id:
        raise HTTPException(403, "Not the owner of this engine")
    return eng


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_user_engines(
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return user's own engines + all public engines."""
    engines = (
        db.query(UserEngine)
        .filter(
            (UserEngine.owner_id == user.id) | (UserEngine.is_public == True)  # noqa: E712
        )
        .order_by(UserEngine.created_at.desc())
        .all()
    )
    return [_engine_dict(e) for e in engines]


@router.post("", status_code=201)
async def create_user_engine(
    body: CreateUserEngineRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.name.strip():
        raise HTTPException(400, "Engine name is required")

    mechanics_raw = [m.model_dump() for m in body.mechanics]
    eng = UserEngine(
        name=body.name.strip(),
        description=body.description,
        owner_id=user.id,
        is_public=body.is_public,
        mechanics=mechanics_raw,
    )
    db.add(eng)
    db.commit()
    db.refresh(eng)
    result = _engine_dict(eng)
    warnings = _collect_mechanic_warnings(mechanics_raw)
    if warnings:
        result["warnings"] = warnings
    return result


@router.get("/{engine_id}")
async def get_user_engine(
    engine_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    eng = db.get(UserEngine, engine_id)
    if not eng:
        raise HTTPException(404, "User engine not found")
    if not eng.is_public and eng.owner_id != user.id:
        raise HTTPException(403, "This engine is private")
    return _engine_dict(eng)


@router.patch("/{engine_id}")
async def update_user_engine(
    engine_id: int,
    body: UpdateUserEngineRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    eng = _get_owned(engine_id, user, db)

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Engine name cannot be empty")
        eng.name = name
    if body.description is not None:
        eng.description = body.description
    if body.is_public is not None:
        eng.is_public = body.is_public
    if body.mechanics is not None:
        eng.mechanics = [m.model_dump() for m in body.mechanics]
    if body.custom_config is not None:
        eng.custom_config = body.custom_config
    if body.disabled_actions is not None:
        eng.disabled_actions = body.disabled_actions

    db.commit()
    db.refresh(eng)
    result = _engine_dict(eng)
    if body.mechanics is not None:
        warnings = _collect_mechanic_warnings(eng.mechanics or [])
        if warnings:
            result["warnings"] = warnings
    return result


@router.delete("/{engine_id}", status_code=204)
async def delete_user_engine(
    engine_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    eng = _get_owned(engine_id, user, db)

    in_use = db.query(GameEngine).filter(
        GameEngine.user_engine_id == engine_id
    ).first()
    if in_use:
        raise HTTPException(409, "Engine is used by one or more games; remove it from games first")

    db.delete(eng)
    db.commit()


@router.post("/{engine_id}/simulate")
async def simulate_user_engine(
    engine_id: int,
    body: SimulateRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test-run an action without a real game. Owner or public engines only."""
    eng = db.get(UserEngine, engine_id)
    if not eng:
        raise HTTPException(404, "User engine not found")
    if not eng.is_public and eng.owner_id != user.id:
        raise HTTPException(403, "This engine is private")

    if eng.base_engine_id:
        # Copy-mode: run action on base engine with custom config
        engine = registry.get_engine(eng.base_engine_id)
        if not engine:
            raise HTTPException(500, f"Base engine '{eng.base_engine_id}' not in registry")
        config = engine.get_default_config()
        config.update(eng.custom_config or {})
        action = body.action or list(engine.get_meta().get("actions", [{}]))[0].get("id", "")
        return engine.handle_action(action, body.payload, config)
    else:
        # Composite mode
        mechanics = eng.mechanics or []
        if not mechanics:
            raise HTTPException(400, "This engine has no mechanics")
        if body.mechanic_index < 0 or body.mechanic_index >= len(mechanics):
            raise HTTPException(400, f"mechanic_index out of range (0..{len(mechanics)-1})")

        mechanic = mechanics[body.mechanic_index]
        primitive = get_primitive(mechanic.get("type"))
        if not primitive:
            raise HTTPException(400, f"Unknown mechanic type: {mechanic.get('type')}")

        action = body.action or mechanic.get("action") or "roll"
        config = mechanic.get("config") or {}
        return primitive.execute(action, body.payload, config)
