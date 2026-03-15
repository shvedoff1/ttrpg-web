"""
primitives/weighted_sample.py — Pick N items from a weighted list without replacement.
"""

import random
from fastapi import HTTPException
from engines.primitives.base import BasePrimitive
from engines._helpers import load_json, get_effective_items


class WeightedSamplePrimitive(BasePrimitive):
    primitive_id = "weighted_sample"
    name = "Выборка без повторов"
    description = "Выбрать N случайных элементов из взвешенного списка без повтора"
    actions = [{"id": "sample", "label": "Выборка"}]

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "default_count", "type": "number", "label": "Количество по умолчанию",
             "default": 3, "min": 1, "max": 20},
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
        if action != "sample":
            raise HTTPException(400, f"Unknown action: {action}")

        if not config.get("data_source"):
            return {"error": True, "html": "Этот движок требует настройки через Категорию. Добавьте привязки ресурсов в настройках категории."}
        data = load_json(config["data_source"])
        items_key = config.get("items_key", "motivations")
        default_count = config.get("default_count", 3)
        count = min(int(payload.get("count", default_count)), 20)

        items = data.get(items_key, []) if isinstance(data, dict) else data
        entries = [
            (item["name"], item.get("weight", 1))
            for item in items
            if isinstance(item, dict) and (item.get("weight") or 0) > 0
        ]

        result: list[str] = []
        available = list(entries)
        for _ in range(min(count, len(available))):
            total = sum(w for _, w in available)
            if total <= 0:
                break
            r = random.random() * total
            chosen_idx = len(available) - 1
            for i, (_, w) in enumerate(available):
                r -= w
                if r <= 0:
                    chosen_idx = i
                    break
            result.append(available[chosen_idx][0])
            available.pop(chosen_idx)

        return {items_key: result}

    def _execute_bindings(self, action: str, payload: dict, config: dict) -> dict:
        if action != "sample":
            raise HTTPException(400, f"Unknown action: {action}")

        bindings = config["_bindings"]
        source_bindings = [b for b in bindings if b.role == "source"]
        if not source_bindings:
            raise HTTPException(422, "No source binding configured")

        items = get_effective_items(source_bindings[0])
        default_count = config.get("default_count", 3)
        count = min(int(payload.get("count", default_count)), 20)

        entries = [
            (item["name"], item["probability"])
            for item in items
            if (item.get("probability") or 0) > 0
        ]

        result: list[str] = []
        available = list(entries)
        for _ in range(min(count, len(available))):
            total = sum(w for _, w in available)
            if total <= 0:
                break
            r = random.random() * total
            chosen_idx = len(available) - 1
            for i, (_, w) in enumerate(available):
                r -= w
                if r <= 0:
                    chosen_idx = i
                    break
            result.append(available[chosen_idx][0])
            available.pop(chosen_idx)

        return {"items": result}
