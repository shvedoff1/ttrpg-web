"""
engines/treasure.py — Treasure roll (random item from weighted categories).

Actions:
  roll → roll a treasure (no payload needed)
"""

import random
from fastapi import HTTPException
from engines.base import BaseEngine
from engines._helpers import load_json

_TREASURE_FILE = "config.treasure.default"


def _roll_treasure(data: dict) -> dict:
    cat_entries = [(k, v) for k, v in data["categories"].items() if (v.get("weight") or 0) > 0]
    if not cat_entries:
        raise HTTPException(500, "treasure.json has no valid categories")

    cat_total = sum(v["weight"] for _, v in cat_entries)
    r = random.random() * cat_total
    chosen_cat_key, chosen_cat = cat_entries[-1]
    for key, v in cat_entries:
        r -= v["weight"]
        if r <= 0:
            chosen_cat_key, chosen_cat = key, v
            break

    items = load_json(chosen_cat["resource_file"])
    entries = [it for it in items.values() if (it.get("probability") or 0) > 0]
    if not entries:
        raise HTTPException(500, f"No items in {chosen_cat['resource_file']}")

    item_total = sum(it["probability"] for it in entries)
    r2 = random.random() * item_total
    chosen = entries[-1]
    for it in entries:
        r2 -= it["probability"]
        if r2 <= 0:
            chosen = it
            break

    return {
        "name": chosen["name"],
        "price": chosen.get("price"),
        "category": chosen_cat["label"],
    }


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
                {
                    "id": "roll",
                    "label": "Найти сокровище",
                    "params": [],
                },
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
            treasure_file = config.get("treasure_file", _TREASURE_FILE)
            data = load_json(treasure_file)
            return _roll_treasure(data)
        raise HTTPException(400, f"Unknown action: {action}")
