"""add probability column to resource_items

Revision ID: i8c9d0e1f2g3
Revises: h7b8c9d0e1f2
Create Date: 2026-03-15
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "i8c9d0e1f2g3"
down_revision: Union[str, None] = "h7b8c9d0e1f2"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Add probability column (default 0)
    op.add_column(
        "resource_items",
        sa.Column("probability", sa.Float(), nullable=False, server_default="0"),
    )
    # Current 'weight' column actually stores probability values from JSON.
    # Copy them to the new probability column, then reset weight to 0.
    # The seed will re-populate correct physical weights on next run.
    op.execute("UPDATE resource_items SET probability = weight, weight = 0")


def downgrade() -> None:
    # Copy probability back to weight before dropping
    op.execute("UPDATE resource_items SET weight = probability")
    op.drop_column("resource_items", "probability")
