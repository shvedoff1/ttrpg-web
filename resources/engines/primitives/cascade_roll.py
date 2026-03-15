"""
primitives/cascade_roll.py — Two-level weighted roll: category → item.
"""

import random
from fastapi import HTTPException
from engines.primitives.base import BasePrimitive
from engines._helpers import load_json, get_effective_items


class CascadeRollPrimitive(BasePrimitive):
    primitive_id = "cascade_roll"
    name = "Каскадный бросок"
    description = "Двухуровневый бросок: сначала категория, потом предмет внутри неё"

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "show_price", "type": "boolean", "label": "Показывать цену"},
        ]}

    def get_binding_schema(self) -> dict:
        return {"roles": [
            {"id": "source", "label": "Категория ресурсов", "multiple": True},
        ]}

    def execute(self, action: str, payload: dict, config: dict) -> dict:
        if config.get("_bindings"):
            return self._execute_bindings(action, payload, config)
        return self._execute_legacy(action, payload, config)

    def _execute_legacy(self, action: str, payload: dict, config: dict) -> dict:
        if action != "roll":
            raise HTTPException(400, f"Unknown action: {action}")

        if not config.get("categories_source"):
            return {"error": True, "html": "Этот движок требует настройки через Категорию. Добавьте привязки ресурсов в настройках категории."}
        data = load_json(config["categories_source"])
        categories = data.get("categories", data)

        cat_entries = [
            (k, v) for k, v in categories.items()
            if isinstance(v, dict) and (v.get("weight") or 0) > 0
        ]
        if not cat_entries:
            raise HTTPException(500, "No valid categories")

        # Roll category
        cat_total = sum(v["weight"] for _, v in cat_entries)
        r = random.random() * cat_total
        chosen_key, chosen_cat = cat_entries[-1]
        for key, v in cat_entries:
            r -= v["weight"]
            if r <= 0:
                chosen_key, chosen_cat = key, v
                break

        # Roll item within category
        items = load_json(chosen_cat["resource_file"])
        entries = [it for it in items.values() if isinstance(it, dict) and (it.get("probability") or 0) > 0]
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
            "weight": chosen.get("weight"),
            "category": chosen_cat.get("label", chosen_key),
        }

    def _execute_bindings(self, action: str, payload: dict, config: dict) -> dict:
        if action != "roll":
            raise HTTPException(400, f"Unknown action: {action}")

        bindings = config["_bindings"]
        source_bindings = [b for b in bindings if b.role == "source"]
        if not source_bindings:
            raise HTTPException(422, "No source bindings configured")

        # Build category entries from bindings
        cat_entries = [
            (b, getattr(b, "category_weight", 1) or 1)
            for b in source_bindings
        ]

        # Roll category by category_weight
        cat_total = sum(w for _, w in cat_entries)
        r = random.random() * cat_total
        chosen_binding = cat_entries[-1][0]
        for b, w in cat_entries:
            r -= w
            if r <= 0:
                chosen_binding = b
                break

        # Roll item from chosen category
        items = get_effective_items(chosen_binding)
        entries = [it for it in items if (it.get("probability") or 0) > 0]
        if not entries:
            label = getattr(chosen_binding, "label", "unknown")
            raise HTTPException(500, f"No items in category: {label}")

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
            "weight": chosen.get("weight"),
            "category": getattr(chosen_binding, "label", None)
                or getattr(chosen_binding, "icon", ""),
        }
