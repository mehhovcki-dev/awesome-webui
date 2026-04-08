"""Add model health check table

Revision ID: e8f9a1b2c3d4
Revises: d9f1c6b7a123, c0fbf31ca0db
Create Date: 2026-04-07 22:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8f9a1b2c3d4"
down_revision: Union[str, tuple[str, str], None] = ("d9f1c6b7a123", "c0fbf31ca0db")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_health_check",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("owned_by", sa.Text(), nullable=True),
        sa.Column("status", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_model_health_check_model_id",
        "model_health_check",
        ["model_id"],
        unique=False,
    )
    op.create_index(
        "ix_model_health_check_checked_at",
        "model_health_check",
        ["checked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_model_health_check_checked_at", table_name="model_health_check")
    op.drop_index("ix_model_health_check_model_id", table_name="model_health_check")
    op.drop_table("model_health_check")
