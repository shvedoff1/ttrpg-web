"""
engines/treasure.py — Treasure roll (random item from weighted categories).

Actions:
  roll → roll a treasure (no payload needed)

Delegates to CascadeRollPrimitive.
"""

from fastapi import HTTPException
from engines.base import BaseEngine
from engines.primitives.cascade_roll import CascadeRollPrimitive

_TREASURE_FILE = "config.treasure.default"

_cascade = CascadeRollPrimitive()


class TreasureEngine(BaseEngine):
    engine_id = "treasure"
    name = "Сокровища"
    description = "Случайное сокровище из взвешенных категорий предметов"

    def get_meta(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "actions": [
                {"id": "roll", "label": "Найти сокровище", "params": []},
            ],
        }

    def get_default_config(self) -> dict:
        return {"treasure_file": _TREASURE_FILE}

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "treasure_file", "type": "slug_picker", "label": "Конфиг сокровищ",
             "slug_type": "engine_config", "engine_filter": "treasure"},
        ]}

    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        if action == "roll":
            return _cascade.execute("roll", payload, {
                "categories_source": config.get("treasure_file", _TREASURE_FILE),
            })
        raise HTTPException(400, f"Unknown action: {action}")
