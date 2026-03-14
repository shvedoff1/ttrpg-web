"""
engines/item_gen.py — Item generator engine (weapons and armor).

Actions:
  generate  → generate items (payload: {category, subtype, count})
  get_types → list available categories and subtypes
"""

from fastapi import HTTPException
from engines.base import BaseEngine
from item_generator import generate_items
from engines._helpers import load_json

_GENERATOR_CONFIG = "config.item_gen.default"


class ItemGenEngine(BaseEngine):
    engine_id = "item_generator"
    name = "Генератор предметов"
    description = "Генерация оружия и брони из частей и свойств"

    def get_meta(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "actions": [
                {
                    "id": "get_types",
                    "label": "Доступные типы",
                    "params": [],
                },
                {
                    "id": "generate",
                    "label": "Сгенерировать",
                    "params": [
                        {"name": "category", "type": "string", "required": True,
                         "hint": "weapon | armor"},
                        {"name": "subtype", "type": "string", "required": True,
                         "hint": "sword, bow, heavy, light, ..."},
                        {"name": "count", "type": "integer", "required": False,
                         "default": 1},
                    ],
                },
            ],
        }

    def get_default_config(self) -> dict:
        return {"config_file": _GENERATOR_CONFIG}

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "config_file", "type": "slug_picker", "label": "Конфиг генератора",
             "slug_type": "engine_config", "engine_filter": "item_generator"},
        ]}

    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        cfg_file = config.get("config_file", _GENERATOR_CONFIG)

        if action == "get_types":
            cfg = load_json(cfg_file)
            result = {}
            for category, subtypes in cfg.items():
                result[category] = list(subtypes.keys())
            return {"types": result}

        if action == "generate":
            category = payload.get("category", "")
            subtype = payload.get("subtype", "")
            count = min(int(payload.get("count", 1)), 100)
            if not category or not subtype:
                raise HTTPException(422, "category and subtype required")
            cfg = load_json(cfg_file)
            if category not in cfg or subtype not in cfg[category]:
                raise HTTPException(422, f"Unknown type: {category}/{subtype}")
            try:
                items = generate_items(category, subtype, count)
                return {"items": items}
            except (ValueError, FileNotFoundError, KeyError) as e:
                raise HTTPException(422, str(e))

        raise HTTPException(400, f"Unknown action: {action}")
