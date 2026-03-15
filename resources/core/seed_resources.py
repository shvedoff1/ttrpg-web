"""
core/seed_resources.py — Сидирование системных ResourceItem из JSON-файлов.

Загружает все предметы в таблицу resource_items при запуске.
Идемпотентно: вставляет новые, обновляет существующие системные предметы.
"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import ResourceItem

_JSONS_DIR = Path(__file__).parent.parent / "jsons"

# (путь к файлу, теги, формат)
# формат: "dict" — {key: {name, price, probability}, ...}, "array" — [{name, weight}, ...]
_RESOURCE_FILES: list[tuple[str, list[str], str]] = [
    # ── Алхимия ──────────────────────────────────────────────────────
    ("resources/алхимия/herbs.json",    ["alchemy", "herb"],    "dict"),
    ("resources/алхимия/potions.json",  ["alchemy", "potion"],  "dict"),
    ("resources/алхимия/reagents.json", ["alchemy", "reagent"], "dict"),

    # ── Охота ────────────────────────────────────────────────────────
    ("resources/охота/arrows.json",   ["hunt", "arrow"],  "dict"),
    ("resources/охота/pelts.json",    ["hunt", "pelt"],   "dict"),
    ("resources/охота/traps.json",    ["hunt", "trap"],   "dict"),
    ("resources/охота/trophies.json", ["hunt", "trophy"], "dict"),

    # ── Провизия ─────────────────────────────────────────────────────
    ("resources/провизия/alcohol.json", ["food", "alcohol"],   "dict"),
    ("resources/провизия/fish.json",    ["food", "fish"],      "dict"),
    ("resources/провизия/food.json",    ["food", "provision"], "dict"),
    ("resources/провизия/spices.json",  ["food", "spice"],     "dict"),

    # ── Прочее ───────────────────────────────────────────────────────
    ("resources/прочее/bags.json",        ["misc", "bag"],       "dict"),
    ("resources/прочее/books.json",       ["misc", "book"],      "dict"),
    ("resources/прочее/candles.json",     ["misc", "candle"],    "dict"),
    ("resources/прочее/cloth.json",       ["misc", "cloth"],     "dict"),
    ("resources/прочее/curiosities.json", ["misc", "curiosity"], "dict"),
    ("resources/прочее/hardware.json",    ["misc", "hardware"],  "dict"),
    ("resources/прочее/hlam.json",        ["misc", "junk"],      "dict"),
    ("resources/прочее/locks.json",       ["misc", "lock"],      "dict"),
    ("resources/прочее/loot.json",        ["misc", "loot"],      "dict"),
    ("resources/прочее/scrolls.json",     ["misc", "scroll"],    "dict"),
    ("resources/прочее/theft.json",       ["misc", "theft"],     "dict"),
    ("resources/прочее/tools.json",       ["misc", "tool"],      "dict"),
    ("resources/прочее/wood.json",        ["misc", "wood"],      "dict"),

    # ── Ремесло ──────────────────────────────────────────────────────
    ("resources/ремесло/armor_parts.json", ["craft", "armor_part"], "dict"),
    ("resources/ремесло/gems.json",        ["craft", "gem"],        "dict"),
    ("resources/ремесло/jewelry.json",     ["craft", "jewelry"],    "dict"),
    ("resources/ремесло/metal.json",       ["craft", "metal"],      "dict"),
    ("resources/ремесло/ores.json",        ["craft", "ore"],        "dict"),
    ("resources/ремесло/weapons.json",     ["craft", "weapon"],     "dict"),

    # ── Генератор: части ─────────────────────────────────────────────
    ("generator/weapon/parts/bases.json",     ["generator", "weapon", "part", "base"],     "dict"),
    ("generator/weapon/parts/materials.json", ["generator", "weapon", "part", "material"], "dict"),
    ("generator/armor/parts/bases.json",      ["generator", "armor", "part", "base"],      "dict"),
    ("generator/armor/parts/materials.json",  ["generator", "armor", "part", "material"],  "dict"),

    # ── Генератор: свойства ──────────────────────────────────────────
    ("generator/weapon/properties/positive.json", ["generator", "weapon", "property", "positive"], "dict"),
    ("generator/weapon/properties/negative.json", ["generator", "weapon", "property", "negative"], "dict"),
    ("generator/armor/properties/positive.json",  ["generator", "armor", "property", "positive"],  "dict"),
    ("generator/armor/properties/negative.json",  ["generator", "armor", "property", "negative"],  "dict"),

    # ── Мотивации ────────────────────────────────────────────────────
    ("configs/motivations.json", ["motivation"], "array:motivations"),
]


def _load_file(rel_path: str) -> dict | list:
    full = (_JSONS_DIR / rel_path).resolve()
    if not full.exists():
        return {}
    return json.loads(full.read_text(encoding="utf-8"))


def _parse_dict_items(data: dict, tags: list[str]) -> list[dict]:
    """Парсит формат {key: {name, price, probability}, _config: {...}}."""
    items = []
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if not isinstance(value, dict):
            continue
        meta = {}
        for field in ("minAmount", "maxAmount", "slot"):
            if field in value:
                meta[field] = value[field]
        items.append({
            "key": key,
            "name": value.get("name", key),
            "price": value.get("price"),
            "weight": value.get("weight", 0),
            "probability": value.get("probability", 0),
            "meta": meta or None,
            "tags": tags,
        })
    return items


def _parse_array_items(data: dict | list, array_key: str, tags: list[str]) -> list[dict]:
    """Парсит формат {key: [{name, weight}, ...]}."""
    if isinstance(data, dict):
        arr = data.get(array_key, [])
    else:
        arr = data
    items = []
    for i, entry in enumerate(arr):
        name = entry.get("name", f"item_{i}")
        # Генерируем key из имени: транслитерация не нужна, используем индекс
        key = f"{array_key}_{i}"
        items.append({
            "key": key,
            "name": name,
            "price": entry.get("price"),
            "weight": entry.get("weight", 0),
            "probability": entry.get("probability", entry.get("weight", 0)),
            "meta": None,
            "tags": tags,
        })
    return items


def seed_resources(db: Session) -> tuple[int, int]:
    """Сидирует системные предметы из JSON-файлов.

    Возвращает (added, updated).
    """
    added = 0
    updated = 0

    # Собираем все существующие системные предметы (owner_id=NULL) в кеш
    existing = {}
    for item in db.execute(
        select(ResourceItem).where(ResourceItem.owner_id.is_(None))
    ).scalars().all():
        existing[item.key] = item

    for path, tags, fmt in _RESOURCE_FILES:
        data = _load_file(path)
        if not data:
            continue

        if fmt == "dict":
            parsed = _parse_dict_items(data, tags)
        elif fmt.startswith("array:"):
            array_key = fmt.split(":", 1)[1]
            parsed = _parse_array_items(data, array_key, tags)
        else:
            continue

        for item_data in parsed:
            key = item_data["key"]
            if key in existing:
                # Обновляем если данные изменились
                ex = existing[key]
                changed = False
                if ex.name != item_data["name"]:
                    ex.name = item_data["name"]
                    changed = True
                if ex.price != item_data["price"]:
                    ex.price = item_data["price"]
                    changed = True
                if ex.weight != item_data["weight"]:
                    ex.weight = item_data["weight"]
                    changed = True
                if ex.probability != item_data["probability"]:
                    ex.probability = item_data["probability"]
                    changed = True
                if ex.tags != item_data["tags"]:
                    ex.tags = item_data["tags"]
                    changed = True
                if ex.meta != item_data["meta"]:
                    ex.meta = item_data["meta"]
                    changed = True
                if changed:
                    updated += 1
            else:
                db.add(ResourceItem(
                    key=key,
                    name=item_data["name"],
                    price=item_data["price"],
                    weight=item_data["weight"],
                    probability=item_data["probability"],
                    meta=item_data["meta"],
                    tags=item_data["tags"],
                    owner_id=None,
                ))
                added += 1

    if added or updated:
        db.commit()

    return added, updated


def run_seed_resources() -> None:
    """Точка входа: запускать при старте приложения."""
    db = SessionLocal()
    try:
        added, updated = seed_resources(db)
        if added or updated:
            print(f"[seed_resources] Добавлено {added}, обновлено {updated} системных ресурсов")
    except Exception as exc:
        print(f"[seed_resources] Ошибка: {exc}")
        db.rollback()
    finally:
        db.close()
