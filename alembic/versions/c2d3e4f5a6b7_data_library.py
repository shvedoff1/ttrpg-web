"""data_library: add data_libraries table for JSON library system

Revision ID: c2d3e4f5a6b7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-14 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_libraries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lib_type", sa.String(length=50), nullable=False),
        sa.Column("engine_id", sa.String(length=100), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("source_slug", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_libraries_slug", "data_libraries", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_data_libraries_slug", table_name="data_libraries")
    op.drop_table("data_libraries")
