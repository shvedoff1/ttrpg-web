"""
routers/bindings.py — CRUD for EngineResourceBinding (engine ↔ resources).

GET    /api/engines/{engine_id}/bindings       — привязки движка
POST   /api/engines/{engine_id}/bindings       — добавить привязку
PATCH  /api/bindings/{id}                      — обновить привязку
DELETE /api/bindings/{id}                      — удалить привязку
POST   /api/engines/{engine_id}/bindings/reorder — изменить порядок
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import EngineResourceBinding, CategoryEngine, EngineCategory

router = APIRouter(tags=["bindings"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class BindingCreate(BaseModel):
    tag_filter: list[str]
    role: str = "source"
    priority: int = 0
    count: Optional[int] = None
    item_overrides: Optional[dict] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    category_weight: Optional[int] = None


class BindingUpdate(BaseModel):
    tag_filter: Optional[list[str]] = None
    role: Optional[str] = None
    priority: Optional[int] = None
    count: Optional[int] = None
    item_overrides: Optional[dict] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    category_weight: Optional[int] = None


class BindingOut(BaseModel):
    id: int
    engine_id: int
    tag_filter: list[str]
    role: str
    priority: int
    count: Optional[int]
    item_overrides: Optional[dict]
    label: Optional[str]
    icon: Optional[str]
    category_weight: Optional[int]
    order: int

    model_config = {"from_attributes": True}


class ReorderRequest(BaseModel):
    binding_ids: list[int]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_engine_ownership(engine_id: int, user: AuthUser, db: Session) -> CategoryEngine:
    """Verify user owns the category containing the engine."""
    engine = db.get(CategoryEngine, engine_id)
    if not engine:
        raise HTTPException(404, "Engine not found")
    category = db.get(EngineCategory, engine.category_id)
    if not category or category.owner_id != user.id:
        raise HTTPException(403, "Нет доступа")
    return engine


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/engines/{engine_id}/bindings", response_model=list[BindingOut])
def list_bindings(
    engine_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _check_engine_ownership(engine_id, user, db)
    return (
        db.query(EngineResourceBinding)
        .filter(EngineResourceBinding.engine_id == engine_id)
        .order_by(EngineResourceBinding.order)
        .all()
    )


@router.post("/api/engines/{engine_id}/bindings", response_model=BindingOut, status_code=201)
def create_binding(
    engine_id: int,
    body: BindingCreate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _check_engine_ownership(engine_id, user, db)

    # Determine next order
    max_order = (
        db.query(EngineResourceBinding.order)
        .filter(EngineResourceBinding.engine_id == engine_id)
        .order_by(EngineResourceBinding.order.desc())
        .first()
    )
    next_order = (max_order[0] + 1) if max_order else 0

    binding = EngineResourceBinding(
        engine_id=engine_id,
        tag_filter=body.tag_filter,
        role=body.role,
        priority=body.priority,
        count=body.count,
        item_overrides=body.item_overrides,
        label=body.label,
        icon=body.icon,
        category_weight=body.category_weight,
        order=next_order,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return binding


@router.patch("/api/bindings/{binding_id}", response_model=BindingOut)
def update_binding(
    binding_id: int,
    body: BindingUpdate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    binding = db.get(EngineResourceBinding, binding_id)
    if not binding:
        raise HTTPException(404, "Binding not found")
    _check_engine_ownership(binding.engine_id, user, db)

    if body.tag_filter is not None:
        binding.tag_filter = body.tag_filter
    if body.role is not None:
        binding.role = body.role
    if body.priority is not None:
        binding.priority = body.priority
    if body.count is not None:
        binding.count = body.count
    if body.item_overrides is not None:
        binding.item_overrides = body.item_overrides
    if body.label is not None:
        binding.label = body.label
    if body.icon is not None:
        binding.icon = body.icon
    if body.category_weight is not None:
        binding.category_weight = body.category_weight

    db.commit()
    db.refresh(binding)
    return binding


@router.delete("/api/bindings/{binding_id}", status_code=204)
def delete_binding(
    binding_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    binding = db.get(EngineResourceBinding, binding_id)
    if not binding:
        raise HTTPException(404, "Binding not found")
    _check_engine_ownership(binding.engine_id, user, db)

    db.delete(binding)
    db.commit()


@router.post("/api/engines/{engine_id}/bindings/reorder")
def reorder_bindings(
    engine_id: int,
    body: ReorderRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    _check_engine_ownership(engine_id, user, db)

    bindings = (
        db.query(EngineResourceBinding)
        .filter(EngineResourceBinding.engine_id == engine_id)
        .all()
    )
    id_to_binding = {b.id: b for b in bindings}

    for i, bid in enumerate(body.binding_ids):
        if bid in id_to_binding:
            id_to_binding[bid].order = i

    db.commit()
    return {"ok": True}
