"""Drop unused user email-verification and quota columns.

Revision ID: 20260901_008
Revises: 20260203_007
Create Date: 2026-09-01

is_verified was never checked (no verification email). api_calls_today was
never incremented. Both stay out until those products exist.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260901_008"
down_revision: Union[str, None] = "20260203_007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_column("users", "api_calls_today")
    op.drop_column("users", "is_verified")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("api_calls_today", sa.String(length=20), nullable=False, server_default="0"),
    )
    op.alter_column("users", "is_verified", server_default=None)
    op.alter_column("users", "api_calls_today", server_default=None)
