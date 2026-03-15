"""
primitives/pool_sample.py — Build inventory from priority-grouped categories.

Loads items from multiple sources (files or item generator),
groups by priority, and samples weighted items.
"""

import logging
from fastapi import HTTPException
from engines.primitives.base import BasePrimitive
from engines._helpers import load_json, sample_weighted, get_effective_items
from item_generator import generate_items

logger = logging.getLogger(__name__)


class PoolSamplePrimitive(BasePrimitive):
    primitive_id = "pool_sample"
    name = "Инвентарь из пулов"
    description = "Сборка инвентаря из приоритетных категорий с генерацией предметов"
    actions = [{"id": "build", "label": "Собрать"}]

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "objects_count", "type": "number",
             "label": "Общее количество предметов", "min": 1},
            {"key": "show_price", "type": "boolean", "label": "Показывать цену"},
        ]}

    def get_binding_schema(self) -> dict:
        return {"roles": [
            {"id": "source", "label": "Источник предметов", "multiple": True},
        ]}

    def execute(self, action: str, payload: dict, config: dict) -> dict:
        if config.get("_bindings"):
            return self._execute_bindings(action, payload, config)
        return self._execute_legacy(action, payload, config)

    def _execute_legacy(self, action: str, payload: dict, config: dict) -> dict:
        if action != "build":
            raise HTTPException(400, f"Unknown action: {action}")

        categories = config.get("categories", [])
        objects_count = config.get("objects_count")
        return {"items": build_from_categories(categories, objects_count)}

    def _execute_bindings(self, action: str, payload: dict, config: dict) -> dict:
        if action != "build":
            raise HTTPException(400, f"Unknown action: {action}")

        bindings = config["_bindings"]
        source_bindings = [b for b in bindings if b.role == "source"]
        if not source_bindings:
            raise HTTPException(422, "No source bindings configured")

        objects_count = config.get("objects_count")

        # Group bindings by priority
        groups: dict[int, list] = {}
        for b in source_bindings:
            p = getattr(b, "priority", 0) or 0
            groups.setdefault(p, []).append(b)

        if objects_count is None:
            objects_count = sum(
                getattr(b, "count", 0) or 0
                for b in source_bindings
            )

        result = {}
        slots = objects_count

        for priority in sorted(groups.keys(), reverse=True):
            if slots <= 0:
                break
            group = groups[priority]

            # Load items from all bindings in this priority group
            pool = []
            for b in group:
                items = get_effective_items(b)
                pool.extend(items)

            sum_count = sum(getattr(b, "count", 0) or 0 for b in group)
            take = min(slots, sum_count)

            entries = [item for item in pool if (item.get("probability") or 0) > 0]

            if entries:
                taken = sample_weighted(entries, take)
                for it in taken:
                    result[it["name"]] = it
                slots -= len(taken)

        return {"items": result}


def build_from_categories(categories: list, objects_count: int | None) -> dict:
    """Build item pool from priority-grouped categories.

    Returns dict of {name: item_data}.
    """
    if objects_count is None:
        objects_count = sum(cat.get("count", 0) for cat in categories)

    groups: dict[int, list] = {}
    for cat in categories:
        p = cat["priority"]
        groups.setdefault(p, []).append(cat)

    result = {}
    slots = objects_count

    for priority in sorted(groups.keys(), reverse=True):
        if slots <= 0:
            break
        group = groups[priority]
        pool = {}
        for cat in group:
            try:
                if "generate" in cat:
                    generated = generate_items(
                        cat["generate"], cat.get("subtype", ""), cat["count"]
                    )
                    for it in generated:
                        pool[it["name"]] = it
                else:
                    pool.update(load_json(cat["resource_file"]))
            except Exception as e:
                logger.error("Failed to build pool for category %s: %s", cat, e)
                raise

        sum_count = sum(c["count"] for c in group)
        take = min(slots, sum_count)
        entries = [it for it in pool.values() if (it.get("probability") or 0) > 0]
        if entries:
            taken = sample_weighted(entries, take)
            for it in taken:
                result[it["name"]] = it
            slots -= len(taken)

    return result
