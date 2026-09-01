"""Add conversations and conversation_messages tables.

Revision ID: 20260202_005
Revises: 20260201_004
Create Date: 2026-02-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260202_005"
down_revision: Union[str, None] = "20260201_004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False, server_default="New Chat"),
        sa.Column("workspace_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pinned_message_ids", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("idx_conversation_user", "conversations", ["user_id"])
    op.create_index("idx_conversation_workspace", "conversations", ["workspace_id"])
    op.create_index("idx_conversation_user_workspace", "conversations", ["user_id", "workspace_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.Text(), nullable=True),
        sa.Column("follow_up_suggestions", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_message_conversation", "conversation_messages", ["conversation_id"])
    op.create_index("idx_message_created", "conversation_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_message_created", table_name="conversation_messages")
    op.drop_index("idx_message_conversation", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    op.drop_index("idx_conversation_user_workspace", table_name="conversations")
    op.drop_index("idx_conversation_workspace", table_name="conversations")
    op.drop_index("idx_conversation_user", table_name="conversations")
    op.drop_table("conversations")
