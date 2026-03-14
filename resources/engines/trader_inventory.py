"""
engines/trader_inventory.py — Trader inventory generation with caching.

Actions:
  list_traders → list available traders (payload: {subtype?})
  get_inventory → get trader inventory (payload: {subtype, key})
  reset_cache   → clear cached inventories
"""

import logging
from typing import Optional
from fastapi import HTTPException
from engines.base import BaseEngine
from engines._helpers import load_json, sample_weighted
from item_generator import generate_items

logger = logging.getLogger(__name__)

_STANDARD_TRADERS = "config.trader.standard"
_STORES_FILE = "config.trader.named"
_TRADER_COEFF_DEFAULT = 1.5

# Per-engine-instance cache
_cache: dict[str, dict] = {}


def _build_inventory(categories: list, objects_count: Optional[int]) -> dict:
    if objects_count is None:
        objects_count = sum(cat.get("count", 0) for cat in categories)

    groups: dict[int, list] = {}
    for cat in categories:
        p = cat["priority"]
        groups.setdefault(p, []).append(cat)

    result = {}
    slots = objects_count

    for priority in sorted(groups.keys(), reverse=True):
        if slots <= 0:
            break
        group = groups[priority]
        pool = {}
        for cat in group:
            try:
                if "generate" in cat:
                    logger.debug("Generating items: type=%s subtype=%s count=%s",
                                 cat["generate"], cat.get("subtype", ""), cat["count"])
                    generated = generate_items(
                        cat["generate"], cat.get("subtype", ""), cat["count"]
                    )
                    for it in generated:
                        pool[it["name"]] = it
                else:
                    logger.debug("Loading resource_file: %s", cat.get("resource_file"))
                    pool.update(load_json(cat["resource_file"]))
            except Exception as e:
                logger.error("Failed to build pool for category %s: %s", cat, e)
                raise

        sum_count = sum(c["count"] for c in group)
        take = min(slots, sum_count)
        entries = [it for it in pool.values() if (it.get("probability") or 0) > 0]
        if entries:
            taken = sample_weighted(entries, take)
            for it in taken:
                result[it["name"]] = it
            slots -= len(taken)

    return result


class TraderInventoryEngine(BaseEngine):
    engine_id = "trader_inventory"
    name = "Инвентарь торговцев"
    description = "Генерация инвентаря стандартных и именных торговцев с кешированием"

    def get_meta(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "actions": [
                {
                    "id": "list_traders",
                    "label": "Список торговцев",
                    "params": [
                        {"name": "subtype", "type": "string", "required": False,
                         "hint": "standard | named (default: all)"}
                    ],
                },
                {
                    "id": "get_inventory",
                    "label": "Получить инвентарь",
                    "params": [
                        {"name": "subtype", "type": "string", "required": True,
                         "hint": "standard | named"},
                        {"name": "key", "type": "string", "required": True},
                    ],
                },
                {
                    "id": "reset_cache",
                    "label": "Сбросить кеш",
                    "params": [],
                },
            ],
        }

    def get_default_config(self) -> dict:
        return {
            "standard_traders_file": _STANDARD_TRADERS,
            "stores_file": _STORES_FILE,
            "coefficient_default": _TRADER_COEFF_DEFAULT,
        }

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "standard_traders_file", "type": "slug_picker",
             "label": "Стандартные торговцы",
             "slug_type": "engine_config", "engine_filter": "trader_inventory"},
            {"key": "stores_file", "type": "slug_picker",
             "label": "Именные магазины",
             "slug_type": "engine_config", "engine_filter": "trader_inventory"},
            {"key": "coefficient_default", "type": "number",
             "label": "Коэффициент цены", "min": 0.1, "max": 10, "step": 0.1},
        ]}

    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        logger.info("trader_inventory action=%s payload=%s", action, payload)
        std_file = config.get("standard_traders_file", _STANDARD_TRADERS)
        stores_file = config.get("stores_file", _STORES_FILE)
        coeff_default = config.get("coefficient_default", _TRADER_COEFF_DEFAULT)

        if action == "reset_cache":
            _cache.clear()
            return {"status": "ok"}

        if action == "list_traders":
            subtype = payload.get("subtype", "all")
            result = []
            if subtype in ("standard", "all"):
                traders = load_json(std_file)
                result += [{"subtype": "standard", "key": k, "name": k}
                           for k in traders]
            if subtype in ("named", "all"):
                stores = load_json(stores_file)
                result += [{"subtype": "named", "key": k, "name": v.get("name", k)}
                           for k, v in stores.items()]
            return {"traders": result}

        if action == "get_inventory":
            subtype = payload.get("subtype")
            key = payload.get("key")
            if not subtype or not key:
                raise HTTPException(422, "subtype and key required")

            cache_key = f"{subtype}:{key}"
            if cache_key in _cache:
                return _cache[cache_key]

            unique_keys: set[str] = set()

            if subtype == "standard":
                traders = load_json(std_file)
                trader = traders.get(key)
                if not trader:
                    raise HTTPException(422, f"Unknown trader: {key}")
                categories = trader.get("categories", [])
                coefficient = trader.get("coefficient", coeff_default)
                pool = _build_inventory(categories, trader.get("objects_count"))

            elif subtype == "named":
                stores = load_json(stores_file)
                store = stores.get(key)
                if not store:
                    raise HTTPException(422, f"Unknown store: {key}")
                categories = store.get("categories", [])
                coefficient = store.get("coefficient", coeff_default)
                pool = _build_inventory(categories, store.get("objects_count"))
                for k, v in (store.get("resources_override") or {}).items():
                    pool[k] = {"probability": 100, **v, "_unique": True}
                    unique_keys.add(k)
            else:
                raise HTTPException(422, f"Unknown subtype: {subtype}")

            items_raw = [
                {
                    "name": it["name"],
                    "probability": it.get("probability", 0),
                    "price": round(it["price"] * coefficient) if it.get("price") else None,
                    "unique": k in unique_keys,
                    "parts": it.get("parts"),
                    "properties": it.get("properties"),
                }
                for k, it in pool.items()
                if (it.get("probability") or 0) > 0
            ]
            items_raw.sort(key=lambda x: x["probability"], reverse=True)
            items = [
                {
                    "name": i["name"],
                    "price": i["price"],
                    "unique": i["unique"],
                    "parts": i["parts"],
                    "properties": i["properties"],
                }
                for i in items_raw
            ]
            result = {"items": items, "coefficient": coefficient}
            _cache[cache_key] = result
            return result

        raise HTTPException(400, f"Unknown action: {action}")
