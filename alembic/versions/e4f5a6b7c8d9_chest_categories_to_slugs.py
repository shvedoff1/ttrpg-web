"""chest_categories_to_slugs: migrate chests_config categories from file paths to slugs

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-03-14 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_DATA = {
    "common": {
        "name": "Деревянный сундук",
        "game": {"length": 3, "directions": ["left", "right"]},
        "gold_min": 0, "gold_max": 25,
        "items_min": 1, "items_max": 2,
        "categories": [
            "items.food.food", "items.food.alcohol", "items.food.spices", "items.food.fish",
            "items.misc.tools", "items.misc.hardware", "items.misc.locks",
            "items.misc.wood", "items.misc.cloth", "items.misc.bags",
            "items.misc.candles", "items.misc.curiosities", "items.misc.hlam"
        ]
    },
    "metal": {
        "name": "Металлический сундук",
        "game": {"length": 4, "directions": ["up", "down", "left", "right"]},
        "gold_min": 20, "gold_max": 80,
        "items_min": 2, "items_max": 3,
        "categories": [
            "items.food.food", "items.food.alcohol", "items.food.spices", "items.food.fish",
            "items.misc.tools", "items.misc.hardware", "items.misc.locks",
            "items.hunt.traps", "items.misc.wood", "items.craft.metal",
            "items.misc.cloth", "items.misc.bags", "items.misc.candles",
            "items.alchemy.potions", "items.misc.scrolls", "items.alchemy.reagents",
            "items.misc.books", "items.misc.curiosities", "items.misc.hlam",
            "items.craft.weapons", "items.craft.armor_parts",
            "items.hunt.arrows", "items.hunt.pelts", "items.hunt.trophies",
            "items.alchemy.herbs"
        ]
    },
    "special": {
        "name": "Особое хранилище",
        "game": {"length": 5, "directions": ["up", "down", "left", "right"]},
        "gold_min": 80, "gold_max": 300,
        "items_min": 3, "items_max": 5,
        "categories": [
            "items.food.food", "items.food.alcohol", "items.food.spices", "items.food.fish",
            "items.misc.tools", "items.misc.hardware", "items.misc.locks",
            "items.hunt.traps", "items.misc.wood", "items.craft.metal",
            "items.misc.cloth", "items.misc.bags", "items.misc.candles",
            "items.craft.jewelry", "items.alchemy.potions", "items.misc.scrolls",
            "items.alchemy.reagents", "items.misc.books", "items.misc.curiosities",
            "items.craft.weapons", "items.craft.armor_parts",
            "items.hunt.arrows", "items.hunt.pelts", "items.hunt.trophies",
            "items.alchemy.herbs"
        ]
    },
    "magic": {
        "name": "Магический сундук",
        "game": {"length": 4, "directions": ["up", "down", "left", "right"]},
        "gold_min": 50, "gold_max": 250,
        "items_min": 2, "items_max": 4,
        "categories": [
            "items.misc.scrolls", "items.alchemy.reagents", "items.alchemy.potions",
            "items.misc.books", "items.misc.curiosities", "items.craft.jewelry",
            "items.alchemy.herbs", "items.food.food", "items.misc.candles",
            "items.misc.cloth", "items.misc.tools", "items.misc.bags",
            "items.misc.hardware", "items.craft.weapons", "items.craft.armor_parts"
        ]
    }
}


def upgrade() -> None:
    import json
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE data_libraries SET data = :data WHERE slug = 'config.chest_game.default'"
        ),
        {"data": json.dumps(_NEW_DATA, ensure_ascii=False)}
    )


def downgrade() -> None:
    # Откат не реализован — старые пути больше не нужны
    pass
