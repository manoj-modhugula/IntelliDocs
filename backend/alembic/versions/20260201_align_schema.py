"""Align schema with current models.

Revision ID: 20260201
Revises: 20260130_002
Create Date: 2026-02-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260201"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Documents: rename legacy columns if present
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='documents' AND column_name='type'
            ) THEN
                ALTER TABLE documents RENAME COLUMN type TO file_type;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='documents' AND column_name='size'
            ) THEN
                ALTER TABLE documents RENAME COLUMN size TO file_size;
            END IF;
        END $$;
        """
    )

    # Documents: add missing columns if needed
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='documents' AND column_name='user_id'
            ) THEN
                ALTER TABLE documents ADD COLUMN user_id VARCHAR(36);
            END IF;
        END $$;
        """
    )

    # Chunks: add workspace_id if missing
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='chunks' AND column_name='workspace_id'
            ) THEN
                ALTER TABLE chunks ADD COLUMN workspace_id VARCHAR(36);
            END IF;
        END $$;
        """
    )

    # Indexes to match model expectations
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunk_workspace ON chunks(workspace_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_document_user ON documents(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_workspace_user ON workspaces(user_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_user_workspace ON documents(user_id, workspace_id)"
    )


def downgrade() -> None:
    # Non-destructive: do not drop columns to avoid data loss.
    pass

