"""engine_improvements: UserEngine copy mode + remove GameEngine.config

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-03-14 12:00:00.000000
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. user_engines: add copy-mode columns ──────────────────────────────
    with op.batch_alter_table("user_engines") as batch:
        batch.add_column(sa.Column("base_engine_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("custom_config", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("source_engine_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("disabled_actions", sa.JSON(), nullable=True))

    # ── 2. game_engines: drop config column ─────────────────────────────────
    with op.batch_alter_table("game_engines") as batch:
        batch.drop_column("config")


def downgrade() -> None:
    with op.batch_alter_table("game_engines") as batch:
        batch.add_column(sa.Column("config", sa.JSON(), nullable=True))

    with op.batch_alter_table("user_engines") as batch:
        batch.drop_column("disabled_actions")
        batch.drop_column("source_engine_id")
        batch.drop_column("custom_config")
        batch.drop_column("base_engine_id")
