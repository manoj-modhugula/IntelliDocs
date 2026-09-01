"""Add skills table for user-defined chat skills (slash commands).

Revision ID: 20260201_004
Revises: 20260201_003
Create Date: 2026-02-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260201_004"
down_revision: Union[str, None] = "20260201_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_skill_user_name", "skills", ["user_id", "name"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_skill_user_name", table_name="skills")
    op.drop_table("skills")
