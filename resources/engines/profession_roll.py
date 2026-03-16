"""
engines/profession_roll.py — Weighted roll by profession and location.

Actions:
  get_professions  → list available professions
  get_locations    → list locations (payload: {profession})
  roll             → execute roll (payload: {profession, location})
  roll_steal       → theft roll (payload: {district})
  roll_cache       → cache/stash roll (payload: {district})

Delegates to ContextRollPrimitive, FilteredRollPrimitive, LootBundlePrimitive.
"""

from fastapi import HTTPException
from engines.base import BaseEngine
from engines._helpers import load_json
from engines.primitives.context_roll import ContextRollPrimitive
from engines.primitives.filtered_roll import FilteredRollPrimitive
from engines.primitives.loot_bundle import LootBundlePrimitive

_DEFAULT_SOURCES: dict[str, tuple[str, str]] = {
    "Травы":  ("items.alchemy.herbs",   "config.profession_roll.herbs"),
    "Руды":   ("items.craft.ores",      "config.profession_roll.ores"),
    "Следы":  ("items.hunt.trophies",   "config.profession_roll.trophies"),
}

_STEAL_CONFIG = "config.profession_roll.steal"
_CACHE_CONFIG = "config.profession_roll.cache"

_context_roll = ContextRollPrimitive()
_filtered_roll = FilteredRollPrimitive()
_loot_bundle = LootBundlePrimitive()

_DISTRICT_NAMES = {
    "poor":   "Бедный район",
    "normal": "Обычный район",
    "rich":   "Богатый район",
    "magic":  "Обитель магии",
}


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
                {"id": "get_professions", "label": "Список профессий", "params": []},
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
            {"key": "enable_steal", "type": "boolean", "label": "Карманная кража"},
            {"key": "enable_cache", "type": "boolean", "label": "Поиск схрона"},
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
        sources = _validate_sources(config.get("sources") or _DEFAULT_SOURCES)

        if action == "get_professions":
            return self._get_professions(sources, config)

        if action == "get_locations":
            return self._get_locations(sources, config, payload)

        if action == "roll":
            return self._roll(sources, payload)

        if action == "roll_steal":
            return self._roll_steal(config, payload)

        if action == "roll_cache":
            return self._roll_cache(config, payload)

        raise HTTPException(400, f"Unknown action: {action}")

    def _get_professions(self, sources: dict, config: dict) -> dict:
        professions = list(sources.keys())
        if config.get("enable_steal", True) or config.get("enable_cache", True):
            professions.append("Воровство")
        return {"professions": professions}

    def _get_locations(self, sources: dict, config: dict, payload: dict) -> dict:
        profession = payload.get("profession", "")

        if profession == "Воровство":
            return self._get_steal_locations(config, payload)

        if profession not in sources:
            raise HTTPException(404, f"Unknown profession: {profession}")

        return _context_roll.execute("list_contexts", {}, {
            "items_source": sources[profession][0],
            "contexts_source": sources[profession][1],
        })

    def _get_steal_locations(self, config: dict, payload: dict) -> dict:
        enable_steal = config.get("enable_steal", True)
        enable_cache = config.get("enable_cache", True)
        param1 = payload.get("param1")

        if param1:
            if param1 == "steal":
                steal_cfg = load_json(config.get("steal_config_file", _STEAL_CONFIG))
                keys = list(steal_cfg.get("district_filter", {}).keys())
            else:
                cache_cfg = load_json(config.get("cache_config_file", _CACHE_CONFIG))
                keys = [k for k, v in cache_cfg.items() if isinstance(v, dict) and "gold_min" in v]
            return {
                "locations": [{"key": k, "name": _DISTRICT_NAMES.get(k, k)} for k in keys]
            }

        modes = []
        if enable_steal:
            modes.append({"key": "steal", "name": "Карманная кража"})
        if enable_cache:
            modes.append({"key": "cache", "name": "Поиск схрона"})

        if len(modes) == 1:
            result = self._get_steal_locations(
                config, {**payload, "param1": modes[0]["key"]}
            )
            result["_mode"] = modes[0]["key"]
            return result

        return {"modes": modes}

    def _roll(self, sources: dict, payload: dict) -> dict:
        profession = payload.get("profession", "")
        if profession not in sources:
            raise HTTPException(422, f"Unknown profession: {profession}")
        location_key = payload.get("location")
        if not location_key:
            raise HTTPException(422, "location required")

        item_file, loc_file = sources[profession]
        return _context_roll.execute("roll", {"context": location_key}, {
            "items_source": item_file,
            "contexts_source": loc_file,
        })

    def _roll_steal(self, config: dict, payload: dict) -> dict:
        district = payload.get("district")
        if not district:
            raise HTTPException(422, "district required")
        return _filtered_roll.execute("roll", {"context": district}, {
            "config_source": config.get("steal_config_file", _STEAL_CONFIG),
        })

    def _roll_cache(self, config: dict, payload: dict) -> dict:
        district = payload.get("district")
        if not district:
            raise HTTPException(422, "district required")
        return _loot_bundle.execute("roll", {"context": district}, {
            "config_source": config.get("cache_config_file", _CACHE_CONFIG),
        })


def _validate_sources(sources: dict) -> dict:
    return {
        k: v for k, v in sources.items()
        if isinstance(v, (list, tuple)) and len(v) == 2 and all(v)
    }
