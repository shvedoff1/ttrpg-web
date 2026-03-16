"""
engines/_helpers.py — Shared JSON loading and roll utilities for all engines.
"""

import json
import logging
import random
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

from fastapi import HTTPException

JSONS_DIR = Path(__file__).parent.parent / "jsons"

# Устанавливается при старте приложения через set_db_resolver()
_db_resolver: Optional[Callable[[str], dict | list]] = None


def set_db_resolver(fn: Callable[[str], dict | list]) -> None:
    """Регистрирует функцию для загрузки библиотек по slug из БД."""
    global _db_resolver
    _db_resolver = fn


def _is_slug(s: str) -> bool:
    """True если строка — slug библиотеки, а не путь к файлу."""
    return not s.endswith(".json")


def load_json(filename: str) -> dict | list:
    # Slug — загружаем из БД через резолвер
    if _is_slug(filename):
        if _db_resolver is None:
            raise HTTPException(500, "DB resolver not initialized")
        return _db_resolver(filename)
    # Путь к файлу — старая логика (backward compat, deprecated)
    logger.warning("load_json: file path '%s' is deprecated, use slug instead", filename)
    if not filename.endswith(".json") or "\\" in filename or ".." in filename:
        raise HTTPException(400, f"Invalid filename: {filename}")
    path = (JSONS_DIR / filename).resolve()
    if not path.is_relative_to(JSONS_DIR.resolve()):
        raise HTTPException(400, f"Invalid filename: {filename}")
    if not path.exists():
        raise HTTPException(404, f"Data file not found: {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


def roll_weighted(resources: dict) -> dict:
    entries = [(name, w) for name, w in resources.items() if (w or 0) > 0]
    if not entries:
        return {"name": "Ничего не нашли"}
    total = sum(w for _, w in entries)
    r = random.random() * total
    for name, w in entries:
        r -= w
        if r <= 0:
            return {"name": name}
    return {"name": entries[-1][0]}


def roll_with_locations(items: dict, location: dict) -> dict:
    overrides = location.get("overrides", {})
    entries = []
    for key, item in items.items():
        if not isinstance(item, dict) or "name" not in item:
            continue
        # Override weight if present, otherwise use base probability
        if key in overrides:
            w = overrides[key]
        else:
            w = item.get("probability", 0)
        if (w or 0) <= 0:
            continue
        entries.append({"name": item["name"], "price": item.get("price"), "w": w})
    if not entries:
        return {"name": "Ничего не нашли"}
    total = sum(e["w"] for e in entries)
    r = random.random() * total
    for e in entries:
        r -= e["w"]
        if r <= 0:
            return {"name": e["name"], "price": e["price"]}
    last = entries[-1]
    return {"name": last["name"], "price": last["price"]}


def validate_config_warnings(primitive_type: str, config: dict | None) -> list[str]:
    """Check if config_source matches the primitive type. Returns warnings list."""
    if primitive_type not in ("filtered_roll", "loot_bundle"):
        return []

    config_source = (config or {}).get("config_source")
    if not config_source:
        return []

    try:
        cfg_data = load_json(config_source)
    except Exception:
        return []

    if not isinstance(cfg_data, dict):
        return []

    has_loot_keys = any(
        isinstance(v, dict) and "gold_min" in v
        for v in cfg_data.values()
    )

    if primitive_type == "filtered_roll" and has_loot_keys:
        return [
            f"Конфиг «{config_source}» содержит настройки лута (gold_min/items_min). "
            f"Возможно, нужен примитив «loot_bundle» вместо «filtered_roll»."
        ]
    if primitive_type == "loot_bundle" and not has_loot_keys:
        return [
            f"Конфиг «{config_source}» не содержит настроек лута (gold_min/items_min). "
            f"Возможно, нужен примитив «filtered_roll» вместо «loot_bundle»."
        ]
    return []


def resolve_bindings(engine_id: int, role: str | None = None) -> list:
    """Загружает привязки ресурсов для данного движка.

    Args:
        engine_id: ID category_engine
        role: опционально фильтр по роли (e.g. "source", "parts:base")

    Returns:
        list[EngineResourceBinding]
    """
    from core.database import SessionLocal
    from core.models import EngineResourceBinding

    db = SessionLocal()
    try:
        q = db.query(EngineResourceBinding).filter(
            EngineResourceBinding.engine_id == engine_id
        )
        if role:
            q = q.filter(EngineResourceBinding.role == role)
        return q.order_by(EngineResourceBinding.priority).all()
    finally:
        db.close()


def get_effective_items(
    binding,
    owner_id: int | None = None,
) -> list[dict]:
    """Загружает ресурсы по тегам привязки, применяет оверрайды.

    Args:
        binding: EngineResourceBinding (с tag_filter и item_overrides)
        owner_id: owner_id для фильтрации (None = системные)

    Returns:
        list[dict] — предметы с применёнными оверрайдами
    """
    from core.database import SessionLocal
    from core.models import ResourceItem

    db = SessionLocal()
    try:
        from sqlalchemy import text, and_
        owner_filter = (
            ResourceItem.owner_id == owner_id if owner_id is not None
            else ResourceItem.owner_id.is_(None)
        )
        # SQLite-compatible: check JSON array contains all tags
        tag_filters = []
        for i, tag in enumerate(binding.tag_filter or []):
            param_name = f"_btag_{i}"
            tag_filters.append(
                text(f"EXISTS (SELECT 1 FROM json_each(resource_items.tags) je WHERE je.value = :{param_name})")
                .bindparams(**{param_name: tag})
            )
        q = db.query(ResourceItem).filter(owner_filter)
        if tag_filters:
            q = q.filter(and_(*tag_filters))
        items = q.all()

        overrides = binding.item_overrides or {}
        result = []
        for item in items:
            effective = {
                "key": item.key,
                "name": item.name,
                "price": item.price,
                "weight": item.weight,
                "probability": item.probability,
                "meta": item.meta or {},
                "tags": item.tags or [],
            }
            if item.key in overrides:
                effective.update(overrides[item.key])
            result.append(effective)
        return result
    finally:
        db.close()


def get_effective_items_multi(
    bindings: list,
    owner_id: int | None = None,
) -> list[dict]:
    """Загружает и объединяет ресурсы из нескольких привязок."""
    result = []
    for binding in bindings:
        result.extend(get_effective_items(binding, owner_id))
    return result


def sample_weighted(entries: list, count: int) -> list:
    available = list(entries)
    result = []
    for _ in range(min(count, len(available))):
        total = sum(it.get("probability", 0) for it in available)
        if total <= 0:
            break
        r = random.random() * total
        chosen_idx = len(available) - 1
        for i, it in enumerate(available):
            r -= it.get("probability", 0)
            if r <= 0:
                chosen_idx = i
                break
        result.append(available[chosen_idx])
        available.pop(chosen_idx)
    return result
