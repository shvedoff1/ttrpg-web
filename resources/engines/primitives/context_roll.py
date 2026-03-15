"""
primitives/context_roll.py — Weighted roll with context-based probability overrides.

Used for profession rolls where location modifies item probabilities.
"""

import random
from fastapi import HTTPException
from engines.primitives.base import BasePrimitive
from engines._helpers import load_json, roll_with_locations, get_effective_items


class ContextRollPrimitive(BasePrimitive):
    primitive_id = "context_roll"
    name = "Бросок с контекстом"
    description = "Взвешенный бросок с модификаторами по контексту (напр. локация)"
    actions = [
        {"id": "roll", "label": "Бросок"},
        {"id": "list_contexts", "label": "Список контекстов"},
    ]

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "show_price", "type": "boolean", "label": "Показывать цену"},
        ]}

    def get_binding_schema(self) -> dict:
        return {"roles": [
            {"id": "source", "label": "Набор ресурсов", "multiple": False},
        ]}

    def execute(self, action: str, payload: dict, config: dict) -> dict:
        if config.get("_bindings"):
            return self._execute_bindings(action, payload, config)
        return self._execute_legacy(action, payload, config)

    def _execute_legacy(self, action: str, payload: dict, config: dict) -> dict:
        items_source = config.get("items_source")
        contexts_source = config.get("contexts_source")
        if not items_source or not contexts_source:
            return {"error": True, "html": "Этот движок требует настройки через Категорию. Добавьте привязки ресурсов в настройках категории."}
        items = load_json(items_source)
        contexts = load_json(contexts_source)

        if action == "list_contexts":
            return {
                "contexts": [
                    {"key": k, "name": v.get("name", k)}
                    for k, v in contexts.items()
                ]
            }

        if action == "roll":
            context_key = payload.get("context")
            if not context_key:
                raise HTTPException(422, "context required")
            context = contexts.get(context_key)
            if not context:
                raise HTTPException(422, f"Unknown context: {context_key}")
            return roll_with_locations(items, context)

        raise HTTPException(400, f"Unknown action: {action}")

    def _execute_bindings(self, action: str, payload: dict, config: dict) -> dict:
        contexts = config.get("contexts", {})

        if action == "list_contexts":
            return {
                "contexts": [
                    {"key": k, "name": v.get("name", k)}
                    for k, v in contexts.items()
                ]
            }

        if action == "roll":
            context_key = payload.get("context")
            if not context_key:
                raise HTTPException(422, "context required")
            context = contexts.get(context_key)
            if not context:
                raise HTTPException(422, f"Unknown context: {context_key}")

            bindings = config["_bindings"]
            source_bindings = [b for b in bindings if b.role == "source"]
            if not source_bindings:
                raise HTTPException(422, "No source binding configured")

            items = get_effective_items(source_bindings[0])
            if not items:
                return {"name": "Ничего не нашли"}

            # Apply context overrides to probability
            # Context is stored as flat {item_key: probability} dict
            overrides = context if isinstance(context, dict) else {}
            entries = []
            for item in items:
                key = item["key"]
                if key in overrides:
                    w = overrides[key]
                else:
                    w = item.get("probability", 0)
                if (w or 0) <= 0:
                    continue
                entries.append({"name": item["name"], "price": item.get("price"), "weight": item.get("weight"), "w": w})

            if not entries:
                return {"name": "Ничего не нашли"}

            total = sum(e["w"] for e in entries)
            r = random.random() * total
            for e in entries:
                r -= e["w"]
                if r <= 0:
                    return {"name": e["name"], "price": e["price"], "weight": e.get("weight")}
            last = entries[-1]
            return {"name": last["name"], "price": last["price"], "weight": last.get("weight")}

        raise HTTPException(400, f"Unknown action: {action}")
