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
