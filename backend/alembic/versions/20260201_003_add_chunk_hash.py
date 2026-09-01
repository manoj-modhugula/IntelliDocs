"""Add content_hash to chunks.

Revision ID: 20260201_003
Revises: 20260201
Create Date: 2026-02-01
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260201_003"
down_revision: Union[str, None] = "20260201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='chunks' AND column_name='content_hash'
            ) THEN
                ALTER TABLE chunks ADD COLUMN content_hash VARCHAR(64);
            END IF;
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunk_content_hash ON chunks(content_hash);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunk_content_hash;")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS content_hash;")
