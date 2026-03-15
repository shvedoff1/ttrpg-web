"""
primitives/filtered_roll.py — Weighted roll with pool filtering by context.

Loads items from multiple sources, sorts by probability,
then filters out rarest/most common based on context rules.
"""

import random
from fastapi import HTTPException
from engines.primitives.base import BasePrimitive
from engines._helpers import load_json, get_effective_items, get_effective_items_multi


class FilteredRollPrimitive(BasePrimitive):
    primitive_id = "filtered_roll"
    name = "Бросок с фильтром"
    description = "Взвешенный бросок с отсечением предметов по контексту (район, уровень)"
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
            districts = cfg.get("district_filter", {})
            return {
                "contexts": [
                    {"key": k, "name": v.get("name", k) if isinstance(v, dict) else k}
                    for k, v in districts.items()
                ],
            }

        if action != "roll":
            raise HTTPException(400, f"Unknown action: {action}")
        context = payload.get("context", "")

        # Build pool from categories
        pool: dict = {}
        for cat_file in cfg.get("categories", []):
            pool.update(load_json(cat_file))

        entries = sorted(
            [(key, data) for key, data in pool.items()
             if isinstance(data, dict) and (data.get("probability") or 0) > 0],
            key=lambda x: x[1]["probability"],
        )
        n = len(entries)
        if n == 0:
            return {"name": "Ничего не нашли"}

        # Apply context filter
        filter_cfg = cfg.get("district_filter", {}).get(context, {})
        ftype = filter_cfg.get("filter", "")
        cut = int(n * filter_cfg.get("percent", 0) / 100)

        if ftype == "exclude_rarest" and cut > 0:
            entries = entries[cut:]
        elif ftype == "exclude_common" and cut > 0:
            entries = entries[:-cut]

        if not entries:
            return {"name": "Ничего не нашли"}

        # Weighted roll
        total = sum(data["probability"] for _, data in entries)
        r = random.random() * total
        for _, data in entries:
            r -= data["probability"]
            if r <= 0:
                return {"name": data["name"], "price": data.get("price"), "weight": data.get("weight")}
        last = entries[-1][1]
        return {"name": last["name"], "price": last.get("price"), "weight": last.get("weight")}

    @staticmethod
    def _normalize_filters(raw) -> list[dict]:
        """Normalize filters to list of {name, field, exclude, mode, value}.

        New format (list):
          [{"name": "Бомжатня", "field": "price", "exclude": "gt", "mode": "percent", "value": 33}]
        Legacy format (list with rule):
          [{"name": "X", "rule": "exclude_rarest", "percent": 58}]
        Legacy format (dict):
          {"key": {"name": "X", "filter": "exclude_rarest", "percent": 30}}
        """
        items = []
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, dict):
                    items.append({"name": v.get("name", k), **v})
                else:
                    items.append({"name": k})
        elif isinstance(raw, list):
            items = list(raw)
        else:
            return []

        result = []
        for item in items:
            # Already new format
            if "field" in item:
                result.append(item)
                continue
            # Legacy: convert rule/filter → new format
            rule = item.get("rule") or item.get("filter", "")
            pct = item.get("percent", 0)
            if rule == "exclude_rarest":
                result.append({
                    "name": item.get("name", ""),
                    "field": "probability",
                    "exclude": "lt",
                    "mode": "percent",
                    "value": pct,
                })
            elif rule == "exclude_common":
                result.append({
                    "name": item.get("name", ""),
                    "field": "probability",
                    "exclude": "gt",
                    "mode": "percent",
                    "value": pct,
                })
            else:
                result.append({"name": item.get("name", ""), **item})
        return result

    @staticmethod
    def _apply_filter(entries: list[dict], f: dict) -> list[dict]:
        """Apply a single filter to the entries list.

        Filter spec: {field, exclude, mode, value}
          field:   "price" | "probability"
          exclude: "gt" (remove items above threshold) | "lt" (remove items below threshold)
          mode:    "percent" (cut top/bottom X% by field) | "absolute" (field value > or < X)
          value:   numeric threshold
        """
        field = f.get("field", "probability")
        exclude = f.get("exclude", "gt")
        mode = f.get("mode", "percent")
        value = f.get("value", 0)

        if not entries or not value:
            return entries

        if mode == "absolute":
            if exclude == "gt":
                return [e for e in entries if (e.get(field) or 0) <= value]
            else:
                return [e for e in entries if (e.get(field) or 0) >= value]
        else:
            # percent — sort by field, cut top or bottom X%
            sorted_by_field = sorted(entries, key=lambda x: x.get(field) or 0)
            n = len(sorted_by_field)
            cut = int(n * value / 100)
            if cut <= 0:
                return entries
            if exclude == "lt":
                # Remove bottom X% (lowest values)
                keep_keys = {id(e) for e in sorted_by_field[cut:]}
            else:
                # Remove top X% (highest values)
                keep_keys = {id(e) for e in sorted_by_field[:-cut]}
            return [e for e in entries if id(e) in keep_keys]

    def _execute_bindings(self, action: str, payload: dict, config: dict) -> dict:
        filters = self._normalize_filters(config.get("filters", {}))

        if action == "list_contexts":
            return {
                "contexts": [
                    {"key": f.get("name", f"filter_{i}"), "name": f.get("name", f"filter_{i}")}
                    for i, f in enumerate(filters)
                ],
            }

        if action != "roll":
            raise HTTPException(400, f"Unknown action: {action}")

        context = payload.get("context", "")

        bindings = config["_bindings"]
        source_bindings = [b for b in bindings if b.role == "source"]
        if not source_bindings:
            raise HTTPException(422, "No source bindings configured")

        # Merge items from all source bindings
        all_items = get_effective_items_multi(source_bindings)

        entries = [item for item in all_items if (item.get("probability") or 0) > 0]
        if not entries:
            return {"name": "Ничего не нашли"}

        # Find selected filter and apply it
        filter_cfg = None
        for f in filters:
            if f.get("name") == context:
                filter_cfg = f
                break

        if filter_cfg:
            entries = self._apply_filter(entries, filter_cfg)

        if not entries:
            return {"name": "Ничего не нашли"}

        # Apply probability overrides from filter
        overrides = filter_cfg.get("overrides", {}) if filter_cfg else {}
        if overrides:
            for item in entries:
                key = item.get("key", item.get("name", ""))
                if key in overrides:
                    item = {**item, "probability": overrides[key]}
            # Rebuild with overrides applied
            entries = [
                {**item, "probability": overrides.get(item.get("key", item.get("name", "")), item.get("probability", 0))}
                for item in entries
            ]
            entries = [e for e in entries if (e.get("probability") or 0) > 0]

        if not entries:
            return {"name": "Ничего не нашли"}

        # Weighted roll
        total = sum(item.get("probability", 0) for item in entries)
        if total <= 0:
            return {"name": "Ничего не нашли"}
        r = random.random() * total
        for item in entries:
            r -= item.get("probability", 0)
            if r <= 0:
                return {"name": item["name"], "price": item.get("price"), "weight": item.get("weight")}
        last = entries[-1]
        return {"name": last["name"], "price": last.get("price"), "weight": last.get("weight")}
