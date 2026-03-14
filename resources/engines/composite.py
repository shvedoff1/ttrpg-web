"""
engines/composite.py — CompositeEngine: runs user-defined mechanics.

A user engine stores a list of mechanics in UserEngine.mechanics:
  [
    {
      "type":   "weighted_roll",   # must match a registered engine_id
      "label":  "Травы",           # display name for this mechanic
      "action": "roll",            # default action to call (optional)
      "config": {...}              # mechanic-specific data overrides
    },
    ...
  ]

When an action is dispatched to CompositeEngine:
  - action format: "<mechanic_label>" or "<mechanic_index>" to pick a mechanic
  - falls back to the first mechanic if only one exists
  - then calls the underlying engine's handle_action with the mechanic's config
"""

from fastapi import HTTPException
from engines.base import BaseEngine
from engines import registry


# Primitive mechanic types available for user engine construction
PRIMITIVE_MECHANICS: list[dict] = [
    {
        "type": "weighted_roll",
        "name": "Взвешенный бросок",
        "description": "Случайный выбор предмета с вероятностями из списка",
        "engine_id": "profession_roll",
        "default_action": "roll",
        "config_schema": {
            "items": "object",       # {key: {name, probability, price?}}
            "locations": "object",   # optional location overrides
        },
    },
    {
        "type": "pick_list",
        "name": "Выбор из списка",
        "description": "Взять N случайных элементов без повтора",
        "engine_id": "story_motivation",
        "default_action": "get_motivations",
        "config_schema": {
            "motivations_file": "string",
        },
    },
    {
        "type": "item_gen",
        "name": "Генератор предметов",
        "description": "Генерация оружия или брони из частей и свойств",
        "engine_id": "item_generator",
        "default_action": "generate",
        "config_schema": {
            "item_gen_file": "string",
        },
    },
    {
        "type": "inventory",
        "name": "Инвентарь торговца",
        "description": "Список товаров торговца с ценами",
        "engine_id": "trader_inventory",
        "default_action": "get_inventory",
        "config_schema": {
            "traders_file": "string",
            "stores_file": "string",
        },
    },
    {
        "type": "loot_table",
        "name": "Таблица лута",
        "description": "Бросок по категориям сокровищ",
        "engine_id": "treasure",
        "default_action": "roll",
        "config_schema": {
            "treasure_file": "string",
        },
    },
]

_PRIMITIVE_MAP: dict[str, dict] = {p["type"]: p for p in PRIMITIVE_MECHANICS}


class CompositeEngine(BaseEngine):
    engine_id = "composite"
    name = "Пользовательский движок"
    description = "Движок, собранный из примитивных механик"

    def get_meta(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "actions": [],
            "primitives": PRIMITIVE_MECHANICS,
        }

    def get_default_config(self) -> dict:
        return {"mechanics": []}

    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        """
        Dispatch action to the appropriate mechanic.

        config must contain:
          - "mechanics": list of mechanic definitions
          - optionally other keys passed through to the underlying engine
        """
        mechanics: list[dict] = config.get("mechanics") or []
        if not mechanics:
            raise HTTPException(400, "This engine has no mechanics configured")

        # Resolve which mechanic to use
        mechanic = _resolve_mechanic(mechanics, action)
        primitive = _PRIMITIVE_MAP.get(mechanic["type"])
        if not primitive:
            raise HTTPException(400, f"Unknown mechanic type: {mechanic['type']}")

        # Get underlying engine from registry
        underlying = registry.get_engine(primitive["engine_id"])
        if not underlying:
            raise HTTPException(500, f"Engine '{primitive['engine_id']}' not registered")

        # Merge mechanic config into call
        mechanic_config = mechanic.get("config") or {}
        resolved_action = mechanic.get("action") or primitive["default_action"]

        return underlying.handle_action(resolved_action, payload, mechanic_config)


def _resolve_mechanic(mechanics: list[dict], action: str) -> dict:
    """
    Find mechanic by label, type, or index.
    Falls back to first mechanic if action is 'default' or only one exists.
    """
    if len(mechanics) == 1 or action in ("default", ""):
        return mechanics[0]

    # Try matching by label
    for m in mechanics:
        if m.get("label") == action or m.get("type") == action:
            return m

    # Try numeric index
    try:
        idx = int(action)
        if 0 <= idx < len(mechanics):
            return mechanics[idx]
    except (ValueError, TypeError):
        pass

    raise HTTPException(400, f"No mechanic found for action: '{action}'")
