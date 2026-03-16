"""
engines/trader_inventory.py — Trader inventory generation with caching.

Actions:
  list_traders → list available traders (payload: {subtype?})
  get_inventory → get trader inventory (payload: {subtype, key})
  reset_cache   → clear cached inventories

Delegates to PoolSamplePrimitive for inventory building.
Caching and price coefficient remain at engine level.
"""

import logging
from fastapi import HTTPException
from engines.base import BaseEngine
from engines._helpers import load_json
from engines.primitives.pool_sample import build_from_categories

logger = logging.getLogger(__name__)

_STANDARD_TRADERS = "config.trader.standard"
_STORES_FILE = "config.trader.named"
_TRADER_COEFF_DEFAULT = 1.5

_cache: dict[str, dict] = {}


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
        std_file = config.get("standard_traders_file", _STANDARD_TRADERS)
        stores_file = config.get("stores_file", _STORES_FILE)
        coeff_default = config.get("coefficient_default", _TRADER_COEFF_DEFAULT)

        if action == "reset_cache":
            _cache.clear()
            return {"status": "ok"}

        if action == "list_traders":
            return self._list_traders(std_file, stores_file, payload)

        if action == "get_inventory":
            return self._get_inventory(
                std_file, stores_file, coeff_default, payload
            )

        raise HTTPException(400, f"Unknown action: {action}")

    def _list_traders(self, std_file: str, stores_file: str, payload: dict) -> dict:
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

    def _get_inventory(self, std_file: str, stores_file: str,
                       coeff_default: float, payload: dict) -> dict:
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
            pool = build_from_categories(categories, trader.get("objects_count"))

        elif subtype == "named":
            stores = load_json(stores_file)
            store = stores.get(key)
            if not store:
                raise HTTPException(422, f"Unknown store: {key}")
            categories = store.get("categories", [])
            coefficient = store.get("coefficient", coeff_default)
            pool = build_from_categories(categories, store.get("objects_count"))
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
