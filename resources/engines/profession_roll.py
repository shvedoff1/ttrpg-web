"""
engines/profession_roll.py — Weighted roll by profession and location.

Actions:
  get_professions  → list available professions
  get_locations    → list locations (payload: {profession})
  roll             → execute roll (payload: {profession, location})
  roll_steal       → theft roll (payload: {district})
  roll_cache       → cache/stash roll (payload: {district})
"""

import random
from fastapi import HTTPException
from engines.base import BaseEngine
from engines._helpers import load_json, roll_with_locations

# Default data sources (Gothic game)
_DEFAULT_SOURCES: dict[str, tuple[str, str]] = {
    "Травы":  ("items.alchemy.herbs",   "config.profession_roll.herbs"),
    "Руды":   ("items.craft.ores",      "config.profession_roll.ores"),
    "Следы":  ("items.hunt.trophies",   "config.profession_roll.trophies"),
}

_STEAL_CONFIG  = "config.profession_roll.steal"
_CACHE_CONFIG  = "config.profession_roll.cache"


def _roll_steal(config: dict, district: str) -> dict:
    pool: dict = {}
    for cat_file in config.get("categories", []):
        pool.update(load_json(cat_file))

    entries = sorted(
        [(key, data) for key, data in pool.items() if (data.get("probability") or 0) > 0],
        key=lambda x: x[1]["probability"],
    )
    n = len(entries)
    if n == 0:
        return {"name": "Ничего не нашли"}

    filter_cfg = config.get("district_filter", {}).get(district, {})
    ftype = filter_cfg.get("filter", "")
    cut = int(n * filter_cfg.get("percent", 0) / 100)

    if ftype == "exclude_rarest" and cut > 0:
        entries = entries[cut:]
    elif ftype == "exclude_common" and cut > 0:
        entries = entries[:-cut]

    if not entries:
        return {"name": "Ничего не нашли"}

    total = sum(data["probability"] for _, data in entries)
    r = random.random() * total
    for _, data in entries:
        r -= data["probability"]
        if r <= 0:
            return {"name": data["name"]}
    return {"name": entries[-1][1]["name"]}


def _roll_cache(config: dict, district: str) -> dict:
    district_cfg = config.get(district)
    if not district_cfg:
        raise HTTPException(422, f"Unknown cache district: {district}")

    gold = random.randint(district_cfg["gold_min"], district_cfg["gold_max"])
    item_count = random.randint(district_cfg["items_min"], district_cfg["items_max"])

    pool: dict = {}
    for cat_file in district_cfg.get("categories", []):
        pool.update(load_json(cat_file))

    entries = [(key, data) for key, data in pool.items() if (data.get("probability") or 0) > 0]
    display_name = district_cfg.get("name", district)

    if not entries:
        return {"name": display_name, "gold": gold, "items": []}

    total = sum(data["probability"] for _, data in entries)
    items: list[str] = []
    for _ in range(item_count):
        r = random.random() * total
        for _, data in entries:
            r -= data["probability"]
            if r <= 0:
                items.append(data["name"])
                break
        else:
            items.append(entries[-1][1]["name"])

    return {"name": display_name, "gold": gold, "items": items}


class ProfessionRollEngine(BaseEngine):
    engine_id = "profession_roll"
    name = "Профессии"
    description = "Взвешенный ролл по локации/профессии (травы, руды, следы, воровство)"

    def get_meta(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "actions": [
                {
                    "id": "get_professions",
                    "label": "Список профессий",
                    "params": [],
                },
                {
                    "id": "get_locations",
                    "label": "Список локаций",
                    "params": [{"name": "profession", "type": "string", "required": True}],
                },
                {
                    "id": "roll",
                    "label": "Сделать ролл",
                    "params": [
                        {"name": "profession", "type": "string", "required": True},
                        {"name": "location", "type": "string", "required": True},
                    ],
                },
                {
                    "id": "roll_steal",
                    "label": "Воровство",
                    "params": [{"name": "district", "type": "string", "required": True}],
                },
                {
                    "id": "roll_cache",
                    "label": "Тайник",
                    "params": [{"name": "district", "type": "string", "required": True}],
                },
            ],
        }

    def get_default_config(self) -> dict:
        return {
            "sources": {k: list(v) for k, v in _DEFAULT_SOURCES.items()},
            "enable_steal": True,
            "enable_cache": True,
            "steal_config_file": _STEAL_CONFIG,
            "cache_config_file": _CACHE_CONFIG,
            "roll_label": "Бросить",
            "show_price": False,
        }

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "sources", "type": "key_value_map", "label": "Профессии",
             "key_label": "Название профессии",
             "value_schema": [
                 {"type": "slug_picker", "label": "Каталог предметов",
                  "slug_type": "item_catalog"},
                 {"type": "slug_picker", "label": "Конфиг локаций",
                  "slug_type": "engine_config", "engine_filter": "profession_roll"},
             ]},
            {"key": "enable_steal", "type": "boolean",
             "label": "Карманная кража"},
            {"key": "enable_cache", "type": "boolean",
             "label": "Поиск схрона"},
            {"key": "steal_config_file", "type": "slug_picker",
             "label": "Конфиг воровства",
             "slug_type": "engine_config", "engine_filter": "profession_roll"},
            {"key": "cache_config_file", "type": "slug_picker",
             "label": "Конфиг тайников",
             "slug_type": "engine_config", "engine_filter": "profession_roll"},
            {"key": "roll_label", "type": "text", "label": "Текст кнопки"},
            {"key": "show_price", "type": "boolean", "label": "Показывать цену"},
        ]}

    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        sources = config.get("sources") or _DEFAULT_SOURCES
        # Validate: each value must be a list/tuple of 2 non-empty slugs
        sources = {k: v for k, v in sources.items()
                   if isinstance(v, (list, tuple)) and len(v) == 2 and all(v)}

        if action == "get_professions":
            professions = list(sources.keys())
            enable_steal = config.get("enable_steal", True)
            enable_cache = config.get("enable_cache", True)
            if enable_steal or enable_cache:
                professions.append("Воровство")
            return {"professions": professions}

        if action == "get_locations":
            profession = payload.get("profession", "")

            if profession == "Воровство":
                enable_steal = config.get("enable_steal", True)
                enable_cache = config.get("enable_cache", True)
                param1 = payload.get("param1")
                if param1:
                    # Return districts for the chosen mode
                    _DISTRICT_NAMES = {
                        "poor":   "Бедный район",
                        "normal": "Обычный район",
                        "rich":   "Богатый район",
                        "magic":  "Обитель магии",
                    }
                    if param1 == "steal":
                        steal_cfg = load_json(config.get("steal_config_file", _STEAL_CONFIG))
                        keys = list(steal_cfg.get("district_filter", {}).keys())
                    else:  # cache
                        cache_cfg = load_json(config.get("cache_config_file", _CACHE_CONFIG))
                        keys = [k for k, v in cache_cfg.items() if isinstance(v, dict)]
                    districts = [{"key": k, "name": _DISTRICT_NAMES.get(k, k)} for k in keys]
                    return {"locations": districts}
                else:
                    # Return available steal modes
                    modes = []
                    if enable_steal:
                        modes.append({"key": "steal", "name": "Карманная кража"})
                    if enable_cache:
                        modes.append({"key": "cache", "name": "Поиск схрона"})
                    if len(modes) == 1:
                        # Only one mode — skip mode selection, go straight to districts
                        result = self.handle_action(
                            "get_locations",
                            {**payload, "param1": modes[0]["key"]},
                            config,
                        )
                        result["_mode"] = modes[0]["key"]
                        return result
                    return {"modes": modes}

            if profession not in sources:
                raise HTTPException(404, f"Unknown profession: {profession}")
            _, loc_file = sources[profession]
            locs = load_json(loc_file)
            return {
                "locations": [{"key": k, "name": v["name"]} for k, v in locs.items()]
            }

        if action == "roll":
            profession = payload.get("profession", "")
            if profession not in sources:
                raise HTTPException(422, f"Unknown profession: {profession}")
            location_key = payload.get("location")
            if not location_key:
                raise HTTPException(422, "location required")
            item_file, loc_file = sources[profession]
            items = load_json(item_file)
            locs = load_json(loc_file)
            location = locs.get(location_key)
            if not location:
                raise HTTPException(422, f"Unknown location: {location_key}")
            return roll_with_locations(items, location)

        if action == "roll_steal":
            district = payload.get("district")
            if not district:
                raise HTTPException(422, "district required")
            steal_cfg = config.get("steal_config_file", _STEAL_CONFIG)
            return _roll_steal(load_json(steal_cfg), district)

        if action == "roll_cache":
            district = payload.get("district")
            if not district:
                raise HTTPException(422, "district required")
            cache_cfg = config.get("cache_config_file", _CACHE_CONFIG)
            return _roll_cache(load_json(cache_cfg), district)

        raise HTTPException(400, f"Unknown action: {action}")
