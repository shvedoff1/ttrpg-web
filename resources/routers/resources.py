"""
routers/resources.py — CRUD for ResourceItem (flat resource items with tags).

GET    /api/resources              — список ресурсов (фильтрация по тегам, owner)
GET    /api/resources/tags         — все уникальные теги
GET    /api/resources/{id}         — один ресурс
POST   /api/resources              — создать пользовательский ресурс
POST   /api/resources/{id}/copy    — скопировать к себе
PATCH  /api/resources/{id}         — обновить (только владелец)
DELETE /api/resources/{id}         — удалить (только владелец)
POST   /api/resources/bulk-copy    — копировать несколько по тегам
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import ResourceItem

router = APIRouter(prefix="/api/resources", tags=["resources"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tags_contain(tag_list: list[str]):
    """Build a filter that checks if ResourceItem.tags JSON array contains all given tags.
    Works with SQLite (json_each) and PostgreSQL (@>).
    """
    from sqlalchemy import and_, literal, text
    # For each tag, check that it exists in the JSON array via json_each
    conditions = []
    for tag in tag_list:
        conditions.append(
            func.json_type(ResourceItem.tags).isnot(None)  # tags is not null
        )
        conditions.append(
            ResourceItem.id.in_(
                func.json_each(ResourceItem.tags).table_valued("value").select()
                .correlate(ResourceItem)
                .where(func.json_each(ResourceItem.tags).table_valued("value").c.value == tag)
                .exists()
            )
        )
    # Simpler approach: use raw SQL for SQLite compatibility
    filters = []
    for tag in tag_list:
        # SQLite: check if tag exists in JSON array using instr on the serialized form
        # More robust: use a subquery with json_each
        filters.append(
            text(f"EXISTS (SELECT 1 FROM json_each(resource_items.tags) WHERE value = :tag_{tag.replace('-','_')})")
            .bindparams(**{f"tag_{tag.replace('-','_')}": tag})
        )
    return and_(*filters)


def _tags_contain_filter(tag_list: list[str]):
    """SQLite-compatible: check if ResourceItem.tags JSON array contains all given tags."""
    from sqlalchemy import and_, text
    filters = []
    for i, tag in enumerate(tag_list):
        param_name = f"_tag_filter_{i}"
        filters.append(
            text(f"EXISTS (SELECT 1 FROM json_each(resource_items.tags) je WHERE je.value = :{param_name})")
            .bindparams(**{param_name: tag})
        )
    return and_(*filters)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ResourceCreate(BaseModel):
    key: str
    name: str
    price: Optional[int] = None
    weight: float = 0
    probability: float = 0
    meta: Optional[dict] = None
    tags: list[str] = []


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    weight: Optional[float] = None
    probability: Optional[float] = None
    meta: Optional[dict] = None
    tags: Optional[list[str]] = None


class ResourceOut(BaseModel):
    id: int
    key: str
    name: str
    price: Optional[int]
    weight: float
    probability: float
    meta: Optional[dict]
    tags: list[str]
    owner_id: Optional[int]
    source_item_id: Optional[int]

    model_config = {"from_attributes": True}


class BulkCopyRequest(BaseModel):
    tags: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ResourceOut])
def list_resources(
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    owner_only: bool = Query(False),
    limit: int = Query(200, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(get_current_user),
):
    """Список ресурсов с фильтрацией по тегам."""
    q = db.query(ResourceItem)

    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            q = q.filter(_tags_contain_filter(tag_list))

    if owner_only:
        if not user:
            raise HTTPException(401, "Требуется авторизация")
        q = q.filter(ResourceItem.owner_id == user.id)
    else:
        filters = [ResourceItem.owner_id.is_(None)]
        if user:
            filters.append(ResourceItem.owner_id == user.id)
        q = q.filter(or_(*filters))

    return q.order_by(ResourceItem.name).offset(offset).limit(limit).all()


@router.get("/tags")
def list_tags(
    owner_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(get_current_user),
):
    """Все уникальные теги из ресурсов. owner_only=true — только из ресурсов пользователя."""
    if owner_only:
        if not user:
            raise HTTPException(401, "Требуется авторизация")
        items = db.query(ResourceItem.tags).filter(ResourceItem.owner_id == user.id).all()
    else:
        filters = [ResourceItem.owner_id.is_(None)]
        if user:
            filters.append(ResourceItem.owner_id == user.id)
        items = db.query(ResourceItem.tags).filter(or_(*filters)).all()
    all_tags = set()
    for (item_tags,) in items:
        if item_tags:
            all_tags.update(item_tags)

    return {"tags": sorted(all_tags)}


@router.get("/count")
def count_by_tags(
    tags: str = Query(..., description="Comma-separated tags"),
    owner_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(get_current_user),
):
    """Подсчёт ресурсов по тегам (для превью в UI)."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    q = db.query(func.count(ResourceItem.id)).filter(
        _tags_contain_filter(tag_list)
    )

    if owner_only:
        if not user:
            raise HTTPException(401, "Требуется авторизация")
        q = q.filter(ResourceItem.owner_id == user.id)
    else:
        filters = [ResourceItem.owner_id.is_(None)]
        if user:
            filters.append(ResourceItem.owner_id == user.id)
        q = q.filter(or_(*filters))

    return {"count": q.scalar()}


@router.get("/{item_id}", response_model=ResourceOut)
def get_resource(
    item_id: int,
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(get_current_user),
):
    item = db.get(ResourceItem, item_id)
    if not item:
        raise HTTPException(404, "Resource not found")
    if item.owner_id is not None and (not user or item.owner_id != user.id):
        raise HTTPException(403, "Нет доступа")
    return item


@router.post("", response_model=ResourceOut, status_code=201)
def create_resource(
    body: ResourceCreate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    existing = db.query(ResourceItem).filter(
        ResourceItem.owner_id == user.id,
        ResourceItem.key == body.key,
    ).first()
    if existing:
        raise HTTPException(409, f"Key уже существует: {body.key}")

    item = ResourceItem(
        key=body.key,
        name=body.name,
        price=body.price,
        weight=body.weight,
        probability=body.probability,
        meta=body.meta,
        tags=body.tags,
        owner_id=user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/copy", response_model=ResourceOut, status_code=201)
def copy_resource(
    item_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    source = db.get(ResourceItem, item_id)
    if not source:
        raise HTTPException(404, "Resource not found")

    # Генерируем уникальный key для копии
    base_key = source.key
    new_key = f"{base_key}_copy"
    n = 2
    while db.query(ResourceItem).filter(
        ResourceItem.owner_id == user.id,
        ResourceItem.key == new_key,
    ).first():
        new_key = f"{base_key}_copy{n}"
        n += 1

    item = ResourceItem(
        key=new_key,
        name=f"{source.name} (копия)",
        price=source.price,
        weight=source.weight,
        meta=source.meta,
        tags=source.tags,
        owner_id=user.id,
        source_item_id=source.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/bulk-copy")
def bulk_copy_by_tags(
    body: BulkCopyRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    """Копирует все системные ресурсы с указанными тегами к пользователю."""
    sources = db.query(ResourceItem).filter(
        ResourceItem.owner_id.is_(None),
        _tags_contain_filter(body.tags),
    ).all()

    existing_keys = set(
        r.key for r in db.query(ResourceItem.key).filter(
            ResourceItem.owner_id == user.id
        ).all()
    )

    copied = 0
    for source in sources:
        if source.key in existing_keys:
            continue
        db.add(ResourceItem(
            key=source.key,
            name=source.name,
            price=source.price,
            weight=source.weight,
            meta=source.meta,
            tags=source.tags,
            owner_id=user.id,
            source_item_id=source.id,
        ))
        copied += 1

    if copied:
        db.commit()

    return {"copied": copied, "skipped": len(sources) - copied}


@router.patch("/{item_id}", response_model=ResourceOut)
def update_resource(
    item_id: int,
    body: ResourceUpdate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    item = db.get(ResourceItem, item_id)
    if not item:
        raise HTTPException(404, "Resource not found")
    if item.owner_id is None:
        raise HTTPException(403, "Системные ресурсы нельзя редактировать")
    if item.owner_id != user.id:
        raise HTTPException(403, "Нет доступа")

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    if body.weight is not None:
        item.weight = body.weight
    if body.probability is not None:
        item.probability = body.probability
    if body.meta is not None:
        item.meta = body.meta
    if body.tags is not None:
        item.tags = body.tags

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_resource(
    item_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    item = db.get(ResourceItem, item_id)
    if not item:
        raise HTTPException(404, "Resource not found")
    if item.owner_id is None:
        raise HTTPException(403, "Системные ресурсы нельзя удалять")
    if item.owner_id != user.id:
        raise HTTPException(403, "Нет доступа")

    db.delete(item)
    db.commit()
