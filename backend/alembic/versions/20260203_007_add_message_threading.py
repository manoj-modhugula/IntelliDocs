"""Add message threading fields.

Revision ID: 20260203_007
Revises: 20260203_006
Create Date: 2026-02-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260203_007"
down_revision: Union[str, None] = "20260203_006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column(
            "parent_id",
            sa.String(36),
            sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_message_parent", "conversation_messages", ["parent_id"])


def downgrade() -> None:
    op.drop_index("idx_message_parent", table_name="conversation_messages")
    op.drop_column("conversation_messages", "parent_id")
