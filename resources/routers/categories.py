"""
routers/categories.py — CRUD for engine categories and their atomic engines.

GET    /api/categories                                  — list (mine + public)
POST   /api/categories                                  — create category
GET    /api/categories/{id}                             — get with engines
PATCH  /api/categories/{id}                             — update (owner only)
DELETE /api/categories/{id}                             — delete (owner only, cascade)

POST   /api/categories/{id}/engines                     — add engine to category
PATCH  /api/categories/{id}/engines/{engine_id}         — update engine
DELETE /api/categories/{id}/engines/{engine_id}         — remove engine
POST   /api/categories/{id}/reorder                     — reorder engines

POST   /api/categories/{id}/engines/{engine_id}/simulate — test-run action
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import EngineCategory, CategoryEngine, GameEngine
from engines import registry
from engines.primitives.registry import get_primitive
from engines._helpers import validate_config_warnings

router = APIRouter(prefix="/api/categories", tags=["categories"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class CreateCategoryRequest(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_public: bool = False


class UpdateCategoryRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    is_public: Optional[bool] = None


class AddCategoryEngineRequest(BaseModel):
    name: str
    description: Optional[str] = None
    engine_type: str  # "primitive" or "system"
    type_id: str      # primitive_id or system engine_id
    config: Optional[dict] = None
    order: int = 0


class UpdateCategoryEngineRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    order: Optional[int] = None


class ReorderRequest(BaseModel):
    order: list[dict]  # [{id: int, order: int}, ...]


class SimulateCategoryEngineRequest(BaseModel):
    action: Optional[str] = None
    payload: dict = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _category_dict(cat: EngineCategory) -> dict:
    return {
        "id": cat.id,
        "name": cat.name,
        "description": cat.description,
        "icon": cat.icon,
        "owner_id": cat.owner_id,
        "is_public": cat.is_public,
        "engines": [_cat_engine_dict(e) for e in cat.engines],
        "created_at": cat.created_at.isoformat() if cat.created_at else None,
    }


def _cat_engine_dict(eng: CategoryEngine) -> dict:
    d = {
        "id": eng.id,
        "category_id": eng.category_id,
        "name": eng.name,
        "description": eng.description,
        "engine_type": eng.engine_type,
        "type_id": eng.type_id,
        "config": eng.config,
        "order": eng.order,
        "created_at": eng.created_at.isoformat() if eng.created_at else None,
    }

    # Add meta for frontend rendering
    if eng.engine_type == "primitive":
        prim = get_primitive(eng.type_id)
        if prim:
            d["meta"] = prim.get_meta()
            d["config_schema"] = prim.get_config_schema()
    elif eng.engine_type == "system":
        engine = registry.get_engine(eng.type_id)
        if engine:
            d["meta"] = engine.get_meta()
            d["config_schema"] = engine.get_config_schema()

    return d


def _get_owned_category(category_id: int, user: AuthUser, db: Session) -> EngineCategory:
    cat = db.get(EngineCategory, category_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    if cat.owner_id != user.id:
        raise HTTPException(403, "Not the owner of this category")
    return cat


def _validate_engine_type(engine_type: str, type_id: str):
    """Validate that engine_type and type_id reference a real primitive or system engine."""
    if engine_type == "primitive":
        if not get_primitive(type_id):
            raise HTTPException(400, f"Unknown primitive: '{type_id}'")
    elif engine_type == "system":
        engine = registry.get_engine(type_id)
        if not engine or type_id == "composite":
            raise HTTPException(400, f"Unknown system engine: '{type_id}'")
    else:
        raise HTTPException(400, f"engine_type must be 'primitive' or 'system', got: '{engine_type}'")


# ── Category CRUD ───────────────────────────────────────────────────────────

@router.get("")
async def list_categories(
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return user's own categories + all public categories."""
    cats = (
        db.query(EngineCategory)
        .filter(
            (EngineCategory.owner_id == user.id) | (EngineCategory.is_public == True)  # noqa: E712
        )
        .order_by(EngineCategory.created_at.desc())
        .all()
    )
    return [_category_dict(c) for c in cats]


@router.post("", status_code=201)
async def create_category(
    body: CreateCategoryRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.name.strip():
        raise HTTPException(400, "Category name is required")

    cat = EngineCategory(
        name=body.name.strip(),
        description=body.description,
        icon=body.icon,
        owner_id=user.id,
        is_public=body.is_public,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return _category_dict(cat)


@router.get("/{category_id}")
async def get_category(
    category_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cat = db.get(EngineCategory, category_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    if not cat.is_public and cat.owner_id != user.id:
        raise HTTPException(403, "This category is private")
    return _category_dict(cat)


@router.patch("/{category_id}")
async def update_category(
    category_id: int,
    body: UpdateCategoryRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cat = _get_owned_category(category_id, user, db)

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Category name cannot be empty")
        cat.name = name
    if body.description is not None:
        cat.description = body.description
    if body.icon is not None:
        cat.icon = body.icon
    if body.is_public is not None:
        cat.is_public = body.is_public

    db.commit()
    db.refresh(cat)
    return _category_dict(cat)


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cat = _get_owned_category(category_id, user, db)

    in_use = db.query(GameEngine).filter(
        GameEngine.engine_category_id == category_id
    ).first()
    if in_use:
        raise HTTPException(409, "Category is used by one or more games; remove it from games first")

    db.delete(cat)
    db.commit()


# ── Engines within category ─────────────────────────────────────────────────

@router.post("/{category_id}/engines", status_code=201)
async def add_category_engine(
    category_id: int,
    body: AddCategoryEngineRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cat = _get_owned_category(category_id, user, db)

    if not body.name.strip():
        raise HTTPException(400, "Engine name is required")

    _validate_engine_type(body.engine_type, body.type_id)

    eng = CategoryEngine(
        category_id=cat.id,
        name=body.name.strip(),
        description=body.description,
        engine_type=body.engine_type,
        type_id=body.type_id,
        config=body.config,
        order=body.order,
    )
    db.add(eng)
    db.commit()
    db.refresh(eng)
    result = _cat_engine_dict(eng)
    if body.engine_type == "primitive":
        warnings = validate_config_warnings(body.type_id, body.config)
        if warnings:
            result["warnings"] = warnings
    return result


@router.patch("/{category_id}/engines/{engine_id}")
async def update_category_engine(
    category_id: int,
    engine_id: int,
    body: UpdateCategoryEngineRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_category(category_id, user, db)

    eng = db.query(CategoryEngine).filter(
        CategoryEngine.id == engine_id,
        CategoryEngine.category_id == category_id,
    ).first()
    if not eng:
        raise HTTPException(404, "Engine not found in this category")

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Engine name cannot be empty")
        eng.name = name
    if body.description is not None:
        eng.description = body.description
    if body.config is not None:
        eng.config = body.config
    if body.order is not None:
        eng.order = body.order

    db.commit()
    db.refresh(eng)
    result = _cat_engine_dict(eng)
    if body.config is not None and eng.engine_type == "primitive":
        warnings = validate_config_warnings(eng.type_id, eng.config)
        if warnings:
            result["warnings"] = warnings
    return result


@router.delete("/{category_id}/engines/{engine_id}", status_code=204)
async def delete_category_engine(
    category_id: int,
    engine_id: int,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_category(category_id, user, db)

    eng = db.query(CategoryEngine).filter(
        CategoryEngine.id == engine_id,
        CategoryEngine.category_id == category_id,
    ).first()
    if not eng:
        raise HTTPException(404, "Engine not found in this category")

    db.delete(eng)
    db.commit()


@router.post("/{category_id}/reorder")
async def reorder_category_engines(
    category_id: int,
    body: ReorderRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_category(category_id, user, db)

    engines = db.query(CategoryEngine).filter(
        CategoryEngine.category_id == category_id
    ).all()
    engine_map = {e.id: e for e in engines}

    for item in body.order:
        eng = engine_map.get(item["id"])
        if eng:
            eng.order = item["order"]

    db.commit()
    return {"ok": True}


# ── Simulate ────────────────────────────────────────────────────────────────

@router.post("/{category_id}/engines/{engine_id}/simulate")
async def simulate_category_engine(
    category_id: int,
    engine_id: int,
    body: SimulateCategoryEngineRequest,
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test-run an action on an engine within a category."""
    cat = db.get(EngineCategory, category_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    if not cat.is_public and cat.owner_id != user.id:
        raise HTTPException(403, "This category is private")

    eng = db.query(CategoryEngine).filter(
        CategoryEngine.id == engine_id,
        CategoryEngine.category_id == category_id,
    ).first()
    if not eng:
        raise HTTPException(404, "Engine not found in this category")

    config = eng.config or {}

    if eng.engine_type == "primitive":
        primitive = get_primitive(eng.type_id)
        if not primitive:
            raise HTTPException(500, f"Primitive '{eng.type_id}' not in registry")
        action = body.action or "roll"
        return primitive.execute(action, body.payload, config)

    elif eng.engine_type == "system":
        engine = registry.get_engine(eng.type_id)
        if not engine:
            raise HTTPException(500, f"System engine '{eng.type_id}' not in registry")
        merged_config = engine.get_default_config()
        merged_config.update(config)
        action = body.action or list(engine.get_meta().get("actions", [{}]))[0].get("id", "")
        return engine.handle_action(action, body.payload, merged_config)

    raise HTTPException(400, f"Unknown engine_type: '{eng.engine_type}'")
