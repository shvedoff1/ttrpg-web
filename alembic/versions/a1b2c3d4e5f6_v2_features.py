"""v2_features: email-based auth, user_engines, game_engines update

Revision ID: a1b2c3d4e5f6
Revises: c4be1ed24337
Create Date: 2026-03-13 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c4be1ed24337"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. users: backfill NULL emails, then make NOT NULL, username nullable ─
    conn = op.get_bind()
    conn.execute(text(
        "UPDATE users SET email = 'user_' || id || '@local' WHERE email IS NULL"
    ))

    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", nullable=False, existing_type=sa.String(255))
        batch.alter_column("username", nullable=True, existing_type=sa.String(100))

    # ── 2. user_engines table ─────────────────────────────────────────────────
    op.create_table(
        "user_engines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("mechanics", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 3. game_engines: add user_engine_id, make engine_id nullable ──────────
    with op.batch_alter_table("game_engines") as batch:
        batch.alter_column("engine_id", nullable=True, existing_type=sa.String(100))
        batch.add_column(sa.Column("user_engine_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_game_engines_user_engine_id",
            "user_engines",
            ["user_engine_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("game_engines") as batch:
        batch.drop_constraint("fk_game_engines_user_engine_id", type_="foreignkey")
        batch.drop_column("user_engine_id")
        batch.alter_column("engine_id", nullable=False, existing_type=sa.String(100))

    op.drop_table("user_engines")

    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", nullable=False, existing_type=sa.String(100))
        batch.alter_column("email", nullable=True, existing_type=sa.String(255))
