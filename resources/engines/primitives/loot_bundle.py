"""
primitives/loot_bundle.py — Generate a loot bundle: gold range + N random items.
"""

import random
from fastapi import HTTPException
from engines.primitives.base import BasePrimitive
from engines._helpers import load_json, get_effective_items, get_effective_items_multi


class LootBundlePrimitive(BasePrimitive):
    primitive_id = "loot_bundle"
    name = "Сбор лута"
    description = "Золото (диапазон) + N случайных предметов из пула"
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
            {"id": "source", "label": "Набор ресурсов", "multiple": True},
        ]}

    def execute(self, action: str, payload: dict, config: dict) -> dict:
        if config.get("_bindings"):
            return self._execute_bindings(action, payload, config)
        return self._execute_legacy(action, payload, config)

    def _execute_legacy(self, action: str, payload: dict, config: dict) -> dict:
        config_source = config.get("config_source")
        if not config_source:
            return {"error": True, "html": "Этот движок требует настройки через Категорию. Добавьте привязки ресурсов в настройках категории."}
        cfg = load_json(config_source)

        if action == "list_contexts":
            return {
                "contexts": [
                    {"key": k, "name": v.get("name", k)}
                    for k, v in cfg.items()
                    if isinstance(v, dict) and "gold_min" in v
                ],
            }

        if action != "roll":
            raise HTTPException(400, f"Unknown action: {action}")
        context = payload.get("context", "")

        district_cfg = cfg.get(context)
        if not district_cfg or not isinstance(district_cfg, dict):
            raise HTTPException(422, f"Unknown context: {context}")

        gold = random.randint(district_cfg["gold_min"], district_cfg["gold_max"])
        item_count = random.randint(district_cfg["items_min"], district_cfg["items_max"])

        # Build pool
        pool: dict = {}
        for cat_file in district_cfg.get("categories", []):
            pool.update(load_json(cat_file))

        entries = [
            (key, data) for key, data in pool.items()
            if isinstance(data, dict) and (data.get("probability") or 0) > 0
        ]
        display_name = district_cfg.get("name", context)

        if not entries:
            return {"name": display_name, "gold": gold, "items": []}

        total = sum(data["probability"] for _, data in entries)
        items: list[str] = []
        for _ in range(item_count):
            r = random.random() * total
            for _, data in entries:
                r -= data["probability"]
                if r <= 0:
                    items.append(data["name"])
                    break
            else:
                items.append(entries[-1][1]["name"])

        return {"name": display_name, "gold": gold, "items": items}

    def _execute_bindings(self, action: str, payload: dict, config: dict) -> dict:
        presets_raw = config.get("presets") or config.get("districts") or {}

        # Normalize: list of dicts → dict keyed by name
        if isinstance(presets_raw, list):
            presets = {p["name"]: p for p in presets_raw if isinstance(p, dict) and p.get("name")}
        else:
            presets = presets_raw

        if action == "list_contexts":
            return {
                "contexts": [
                    {"key": k, "name": v.get("name", k)}
                    for k, v in presets.items()
                ],
            }

        if action != "roll":
            raise HTTPException(400, f"Unknown action: {action}")

        context = payload.get("context", "")
        preset_cfg = presets.get(context)
        if not preset_cfg or not isinstance(preset_cfg, dict):
            raise HTTPException(422, f"Unknown context: {context}")

        gold = random.randint(preset_cfg["gold_min"], preset_cfg["gold_max"])
        item_count = random.randint(preset_cfg["items_min"], preset_cfg["items_max"])

        bindings = config["_bindings"]
        source_bindings = [b for b in bindings if b.role == "source"]

        # Merge items from all source bindings
        all_items = get_effective_items_multi(source_bindings)
        entries = [item for item in all_items if (item.get("probability") or 0) > 0]

        # Apply probability overrides from preset
        overrides = preset_cfg.get("overrides", {})
        if overrides:
            entries = [
                {**item, "probability": overrides.get(item.get("key", item.get("name", "")), item.get("probability", 0))}
                for item in entries
            ]
            entries = [e for e in entries if (e.get("probability") or 0) > 0]

        display_name = preset_cfg.get("name", context)

        if not entries:
            return {"name": display_name, "gold": gold, "items": []}

        total = sum(item["probability"] for item in entries)
        items: list[str] = []
        for _ in range(item_count):
            r = random.random() * total
            for item in entries:
                r -= item["probability"]
                if r <= 0:
                    items.append(item["name"])
                    break
            else:
                items.append(entries[-1]["name"])

        return {"name": display_name, "gold": gold, "items": items}
