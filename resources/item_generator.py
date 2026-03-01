"""
Item generator module — generates weapons and armor with randomized parts and properties.
"""

import json
import random
from pathlib import Path
from typing import Union

RESOURCES_DIR = Path(__file__).parent / "jsons"
GENERATOR_CONFIG_FILE = "configs/item_generator.json"


def _load_json(filename: str) -> Union[dict, list]:
    """Load JSON from jsons directory."""
    path = RESOURCES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


def _pick_one(items: dict) -> dict:
    """Pick a single item from a dict using weighted probability."""
    entries = [(k, v) for k, v in items.items() if v.get("probability", 0) > 0]
    if not entries:
        raise ValueError("No items with positive probability")

    total = sum(v["probability"] for _, v in entries)
    r = random.random() * total

    for _, item in entries:
        r -= item["probability"]
        if r <= 0:
            return item

    return entries[-1][1]


def _pick_many(items: dict, count: int) -> list:
    """Pick multiple items from a dict without replacement, weighted by probability."""
    available = list(items.values())
    result = []

    for _ in range(min(count, len(available))):
        total = sum(it.get("probability", 0) for it in available)
        if total <= 0:
            break

        r = random.random() * total
        chosen_idx = len(available) - 1

        for i, it in enumerate(available):
            r -= it.get("probability", 0)
            if r <= 0:
                chosen_idx = i
                break

        result.append(available[chosen_idx])
        available.pop(chosen_idx)

    return result


def generate_item(category: str, subtype: str) -> dict:
    """Generate a single item (weapon or armor) with parts and properties.

    Returns:
        {
            "name": "Part 1, Part 2, Part 3",
            "price": 280,
            "probability": 100,
            "parts": ["Part 1 name", "Part 2 name", "Part 3 name"],
            "properties": ["Property 1 name", "Property 2 name"]
        }
    """
    config = _load_json(GENERATOR_CONFIG_FILE)

    if category not in config:
        raise ValueError(f"Unknown item category: {category}")

    type_config = config[category].get(subtype)
    if not type_config:
        raise ValueError(f"Unknown {category} subtype: {subtype}")

    parts = []
    parts_price = 0

    # Pick one part from each slot
    for part_slot in type_config["parts"]:
        slot_items = _load_json(part_slot["source"])
        chosen_part = _pick_one(slot_items)
        parts.append(chosen_part)
        parts_price += chosen_part.get("price", 0)

    # Pick properties from each group
    properties = []
    properties_price = 0

    for prop_group in type_config.get("property_groups", []):
        count = random.randint(prop_group["count_min"], prop_group["count_max"])
        if count > 0:
            prop_items = _load_json(prop_group["source"])
            chosen_props = _pick_many(prop_items, count)
            for prop in chosen_props:
                properties.append(prop)
                properties_price += prop.get("price", 0)

    # Calculate final price (never negative)
    final_price = max(0, parts_price + properties_price)

    # Build display names
    parts_names = [part["name"] for part in parts]
    properties_names = [prop["name"] for prop in properties]

    return {
        "name": ", ".join(parts_names),
        "price": final_price,
        "probability": 100,
        "parts": parts_names,
        "properties": properties_names,
    }


def generate_items(category: str, subtype: str, count: int) -> list:
    """Generate multiple items of the same type."""
    return [generate_item(category, subtype) for _ in range(count)]
