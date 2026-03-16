"""
routers/libraries.py — CRUD for DataLibrary (data collections).

GET    /api/libraries              — список доступных библиотек (без data)
GET    /api/libraries/{slug}       — полные данные библиотеки (с data)
POST   /api/libraries              — создать пользовательскую библиотеку
POST   /api/libraries/{slug}/copy  — скопировать в свою
PATCH  /api/libraries/{slug}       — обновить (только владелец)
DELETE /api/libraries/{slug}       — удалить (только владелец)
"""

import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import AuthUser, get_current_user
from core.models import DataLibrary

router = APIRouter(prefix="/api/libraries", tags=["libraries"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LibraryCreate(BaseModel):
    slug: Optional[str] = None
    name: str
    description: Optional[str] = None
    lib_type: str  # item_catalog | engine_config | generator_props
    engine_id: Optional[str] = None
    is_public: bool = False
    data: dict | list


class LibraryCopy(BaseModel):
    new_slug: Optional[str] = None
    new_name: Optional[str] = None


class LibraryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    data: Optional[dict | list] = None


class LibraryOut(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str]
    lib_type: str
    engine_id: Optional[str]
    owner_id: Optional[int]
    is_public: bool
    source_slug: Optional[str]
    preview: Optional[list[str]] = None

    model_config = {"from_attributes": True}


def _build_preview(lib: DataLibrary) -> list[str]:
    data = lib.data
    if not isinstance(data, dict):
        return []
    if lib.lib_type == "item_catalog":
        names = []
        for v in data.values():
            if isinstance(v, dict) and "name" in v:
                names.append(v["name"])
            if len(names) >= 5:
                break
        return names
    elif lib.lib_type == "generator_props":
        return list(data.keys())[:5]
    else:
        # engine_config: top-level keys (chest types, trader types, etc.)
        return list(data.keys())[:8]


class LibraryDetailOut(LibraryOut):
    data: dict | list


# ── Helpers ───────────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,198}[a-z0-9]$")


def _validate_slug(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        raise HTTPException(422, "Slug может содержать только строчные буквы, цифры, '.', '-', '_'")
    return slug


def _auto_slug(name: str, owner_id: int) -> str:
    base = re.sub(r"[^a-z0-9]", "-", name.lower())[:30].strip("-") or "lib"
    suffix = uuid.uuid4().hex[:6]
    return f"user.{owner_id}.{base}-{suffix}"


def _unique_slug(base_slug: str, db: Session) -> str:
    """Return base_slug if available, otherwise append -2, -3, ... until unique."""
    if not db.query(DataLibrary).filter(DataLibrary.slug == base_slug).first():
        return base_slug
    n = 2
    while True:
        candidate = f"{base_slug}-{n}"
        if not db.query(DataLibrary).filter(DataLibrary.slug == candidate).first():
            return candidate
        n += 1


def _get_library(slug: str, db: Session) -> DataLibrary:
    row = db.query(DataLibrary).filter(DataLibrary.slug == slug).first()
    if not row:
        raise HTTPException(404, f"Library not found: {slug}")
    return row


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[LibraryOut])
def list_libraries(
    lib_type: Optional[str] = Query(None),
    engine_id: Optional[str] = Query(None),
    include_system: bool = Query(True),
    owner_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(get_current_user),
):
    """Список библиотек без data-поля (лёгкий)."""
    q = db.query(DataLibrary)

    if lib_type:
        q = q.filter(DataLibrary.lib_type == lib_type)
    if engine_id:
        q = q.filter(DataLibrary.engine_id == engine_id)

    if owner_only:
        if not user:
            raise HTTPException(401, "Требуется авторизация")
        q = q.filter(DataLibrary.owner_id == user.id)
    else:
        # Системные + публичные + свои
        filters = [DataLibrary.is_public == True]  # noqa: E712
        if include_system:
            filters.append(DataLibrary.owner_id.is_(None))
        if user:
            filters.append(DataLibrary.owner_id == user.id)

        from sqlalchemy import or_
        q = q.filter(or_(*filters))

    rows = q.order_by(DataLibrary.lib_type, DataLibrary.name).all()
    result = []
    for r in rows:
        out = LibraryOut.model_validate(r)
        out.preview = _build_preview(r)
        result.append(out)
    return result


@router.get("/{slug}", response_model=LibraryDetailOut)
def get_library(
    slug: str,
    db: Session = Depends(get_db),
    user: Optional[AuthUser] = Depends(get_current_user),
):
    row = _get_library(slug, db)
    # Системные и публичные — доступны всем. Приватные — только владельцу.
    if row.owner_id is not None and not row.is_public:
        if not user or row.owner_id != user.id:
            raise HTTPException(403, "Нет доступа")
    return LibraryDetailOut.model_validate(row)


@router.post("", response_model=LibraryDetailOut, status_code=201)
def create_library(
    body: LibraryCreate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    slug = _validate_slug(body.slug) if body.slug else _auto_slug(body.name, user.id)

    if db.query(DataLibrary).filter(DataLibrary.slug == slug).first():
        raise HTTPException(409, f"Slug уже занят: {slug}")

    row = DataLibrary(
        slug=slug,
        name=body.name,
        description=body.description,
        lib_type=body.lib_type,
        engine_id=body.engine_id,
        owner_id=user.id,
        is_public=body.is_public,
        data=body.data,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return LibraryDetailOut.model_validate(row)


@router.post("/{slug}/copy", response_model=LibraryDetailOut, status_code=201)
def copy_library(
    slug: str,
    body: LibraryCopy,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    source = _get_library(slug, db)

    if body.new_slug:
        new_slug = _validate_slug(body.new_slug)
        if db.query(DataLibrary).filter(DataLibrary.slug == new_slug).first():
            raise HTTPException(409, f"Slug уже занят: {new_slug}")
    else:
        new_slug = _unique_slug(source.slug, db)

    row = DataLibrary(
        slug=new_slug,
        name=body.new_name or f"{source.name} (копия)",
        description=source.description,
        lib_type=source.lib_type,
        engine_id=source.engine_id,
        owner_id=user.id,
        is_public=False,
        data=source.data,
        source_slug=source.slug,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return LibraryDetailOut.model_validate(row)


@router.patch("/{slug}", response_model=LibraryDetailOut)
def update_library(
    slug: str,
    body: LibraryUpdate,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    row = _get_library(slug, db)
    if row.owner_id is None:
        raise HTTPException(403, "Системные библиотеки нельзя редактировать")
    if row.owner_id != user.id:
        raise HTTPException(403, "Нет доступа")

    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.is_public is not None:
        row.is_public = body.is_public
    if body.data is not None:
        row.data = body.data

    db.commit()
    db.refresh(row)
    return LibraryDetailOut.model_validate(row)


@router.delete("/{slug}", status_code=204)
def delete_library(
    slug: str,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    row = _get_library(slug, db)
    if row.owner_id is None:
        raise HTTPException(403, "Системные библиотеки нельзя удалять")
    if row.owner_id != user.id:
        raise HTTPException(403, "Нет доступа")

    db.delete(row)
    db.commit()
