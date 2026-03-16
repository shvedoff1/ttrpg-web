"""
primitives/item_generator.py — Generate weapons and armor from parts and properties.
"""

import random
from fastapi import HTTPException
from engines.primitives.base import BasePrimitive
from engines._helpers import load_json, get_effective_items
from item_generator import generate_items


class ItemGeneratorPrimitive(BasePrimitive):
    primitive_id = "item_generator"
    name = "Генератор предметов"
    description = "Генерация оружия и брони из частей и свойств"
    actions = [
        {"id": "generate", "label": "Сгенерировать"},
        {"id": "get_types", "label": "Типы предметов"},
    ]

    def get_config_schema(self) -> dict:
        return {"fields": []}

    def get_binding_schema(self) -> dict:
        return {"roles": [
            {"id": "parts:base", "label": "Базовые части", "multiple": False},
            {"id": "parts:material", "label": "Материалы", "multiple": False},
            {"id": "props:positive", "label": "Положительные свойства", "multiple": False},
            {"id": "props:negative", "label": "Отрицательные свойства", "multiple": False},
        ]}

    def execute(self, action: str, payload: dict, config: dict) -> dict:
        if config.get("_bindings"):
            return self._execute_bindings(action, payload, config)
        return self._execute_legacy(action, payload, config)

    def _execute_legacy(self, action: str, payload: dict, config: dict) -> dict:
        cfg_file = config.get("config_file", "config.item_gen.default")

        if action == "get_types":
            cfg = load_json(cfg_file)
            return {"types": {cat: list(subs.keys()) for cat, subs in cfg.items()}}

        if action == "generate":
            category = payload.get("category", "")
            subtype = payload.get("subtype", "")
            count = min(int(payload.get("count", 1)), 100)
            if not category or not subtype:
                raise HTTPException(422, "category and subtype required")
            cfg = load_json(cfg_file)
            if category not in cfg or subtype not in cfg[category]:
                raise HTTPException(422, f"Unknown type: {category}/{subtype}")
            items = generate_items(category, subtype, count)
            return {"items": items}

        raise HTTPException(400, f"Unknown action: {action}")

    def _execute_bindings(self, action: str, payload: dict, config: dict) -> dict:
        templates = config.get("templates", {})

        if action == "get_types":
            return {"types": {k: list(v.keys()) if isinstance(v, dict) else [] for k, v in templates.items()}}

        if action == "generate":
            category = payload.get("category", "")
            subtype = payload.get("subtype", "")
            count = min(int(payload.get("count", 1)), 100)
            if not category or not subtype:
                raise HTTPException(422, "category and subtype required")
            if category not in templates or subtype not in templates.get(category, {}):
                raise HTTPException(422, f"Unknown type: {category}/{subtype}")

            bindings = config["_bindings"]

            # Load parts and properties from bindings by role
            parts_base = self._get_items_for_role(bindings, "parts:base")
            parts_material = self._get_items_for_role(bindings, "parts:material")
            props_positive = self._get_items_for_role(bindings, "props:positive")
            props_negative = self._get_items_for_role(bindings, "props:negative")

            template = templates[category][subtype]
            items = []
            for _ in range(count):
                item = self._generate_single(
                    template, parts_base, parts_material,
                    props_positive, props_negative,
                )
                items.append(item)

            return {"items": items}

        raise HTTPException(400, f"Unknown action: {action}")

    @staticmethod
    def _get_items_for_role(bindings: list, role: str) -> list[dict]:
        """Get effective items for a specific binding role."""
        role_bindings = [b for b in bindings if b.role == role]
        if not role_bindings:
            return []
        return get_effective_items(role_bindings[0])

    @staticmethod
    def _pick_weighted(items: list[dict]) -> dict | None:
        """Pick a single item from list by weight."""
        if not items:
            return None
        valid = [it for it in items if (it.get("probability") or 0) > 0]
        if not valid:
            return None
        total = sum(it["probability"] for it in valid)
        r = random.random() * total
        for it in valid:
            r -= it["probability"]
            if r <= 0:
                return it
        return valid[-1]

    def _generate_single(
        self,
        template: dict,
        parts_base: list[dict],
        parts_material: list[dict],
        props_positive: list[dict],
        props_negative: list[dict],
    ) -> dict:
        """Generate a single item from parts and properties."""
        base = self._pick_weighted(parts_base)
        material = self._pick_weighted(parts_material)

        # Build name
        name_parts = []
        if material:
            name_parts.append(material["name"])
        if base:
            name_parts.append(base["name"])
        name = " ".join(name_parts) if name_parts else "Неизвестный предмет"

        # Pick properties
        pos_count = template.get("positive_props", 1)
        neg_count = template.get("negative_props", 0)

        positive = []
        available_pos = [p for p in props_positive if (p.get("probability") or 0) > 0]
        for _ in range(min(pos_count, len(available_pos))):
            picked = self._pick_weighted(available_pos)
            if picked:
                positive.append(picked["name"])
                available_pos = [p for p in available_pos if p["key"] != picked["key"]]

        negative = []
        available_neg = [p for p in props_negative if (p.get("probability") or 0) > 0]
        for _ in range(min(neg_count, len(available_neg))):
            picked = self._pick_weighted(available_neg)
            if picked:
                negative.append(picked["name"])
                available_neg = [p for p in available_neg if p["key"] != picked["key"]]

        # Calculate price
        base_price = (base or {}).get("price", 0) or 0
        material_mult = (material or {}).get("meta", {}).get("price_mult", 1)
        price = int(base_price * material_mult)

        return {
            "name": name,
            "price": price,
            "properties": positive,
            "negative_properties": negative,
            "base": (base or {}).get("name", ""),
            "material": (material or {}).get("name", ""),
        }
