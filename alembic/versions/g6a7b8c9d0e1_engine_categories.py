"""engine_categories: add EngineCategory + CategoryEngine tables, extend GameEngine

Revision ID: g6a7b8c9d0e1
Revises: f5a6b7c8d9e0
Create Date: 2026-03-15 12:00:00.000000
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "g6a7b8c9d0e1"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- engine_categories ---
    op.create_table(
        "engine_categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("icon", sa.String(10), nullable=True),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- category_engines ---
    op.create_table(
        "category_engines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "category_id",
            sa.Integer,
            sa.ForeignKey("engine_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("engine_type", sa.String(20), nullable=False),
        sa.Column("type_id", sa.String(100), nullable=False),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- extend game_engines ---
    op.add_column(
        "game_engines",
        sa.Column(
            "engine_category_id",
            sa.Integer,
            sa.ForeignKey("engine_categories.id"),
            nullable=True,
        ),
    )

    # Drop old constraint and create new one (exactly one of three must be set)
    op.drop_constraint("ck_game_engines_one_source", "game_engines", type_="check")
    op.create_check_constraint(
        "ck_game_engines_one_source",
        "game_engines",
        "(CASE WHEN engine_id IS NOT NULL THEN 1 ELSE 0 END"
        " + CASE WHEN user_engine_id IS NOT NULL THEN 1 ELSE 0 END"
        " + CASE WHEN engine_category_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_game_engines_one_source", "game_engines", type_="check")
    op.drop_column("game_engines", "engine_category_id")
    op.create_check_constraint(
        "ck_game_engines_one_source",
        "game_engines",
        "(engine_id IS NOT NULL) != (user_engine_id IS NOT NULL)",
    )
    op.drop_table("category_engines")
    op.drop_table("engine_categories")
