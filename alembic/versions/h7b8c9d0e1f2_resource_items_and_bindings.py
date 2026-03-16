"""resource_items and engine_resource_bindings

Revision ID: h7b8c9d0e1f2
Revises: g6a7b8c9d0e1
Create Date: 2026-03-15
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "h7b8c9d0e1f2"
down_revision: Union[str, None] = "g6a7b8c9d0e1"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "resource_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "source_item_id",
            sa.Integer(),
            sa.ForeignKey("resource_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "key", name="uq_resource_items_owner_key"),
    )

    op.create_table(
        "engine_resource_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "engine_id",
            sa.Integer(),
            sa.ForeignKey("category_engines.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("tag_filter", sa.JSON(), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="source"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("count", sa.Integer(), nullable=True),
        sa.Column("item_overrides", sa.JSON(), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("icon", sa.String(10), nullable=True),
        sa.Column("category_weight", sa.Integer(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("engine_resource_bindings")
    op.drop_table("resource_items")
