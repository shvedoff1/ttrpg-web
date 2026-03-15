"""
engines/item_gen.py — Item generator engine (weapons and armor).

Actions:
  generate  → generate items (payload: {category, subtype, count})
  get_types → list available categories and subtypes

Delegates to ItemGeneratorPrimitive.
"""

from fastapi import HTTPException
from engines.base import BaseEngine
from engines.primitives.item_generator import ItemGeneratorPrimitive

_GENERATOR_CONFIG = "config.item_gen.default"

_gen = ItemGeneratorPrimitive()


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
                {"id": "get_types", "label": "Доступные типы", "params": []},
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
        return _gen.execute(action, payload, {"config_file": cfg_file})
