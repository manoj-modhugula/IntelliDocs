"""Add table/figure geometry and CLIP embeddings on chunks.

Revision ID: 20260901_009
Revises: 20260901_008
Create Date: 2026-09-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260901_009"
down_revision: Union[str, None] = "20260901_008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column("chunk_type", sa.String(length=16), nullable=False, server_default="text"),
    )
    op.add_column("chunks", sa.Column("bbox_x0", sa.Float(), nullable=True))
    op.add_column("chunks", sa.Column("bbox_y0", sa.Float(), nullable=True))
    op.add_column("chunks", sa.Column("bbox_x1", sa.Float(), nullable=True))
    op.add_column("chunks", sa.Column("bbox_y1", sa.Float(), nullable=True))
    op.add_column("chunks", sa.Column("image_key", sa.String(length=500), nullable=True))
    op.add_column("chunks", sa.Column("caption", sa.Text(), nullable=True))
    op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS clip_embedding vector(512)")
    op.create_index("idx_chunk_type", "chunks", ["chunk_type"])
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_clip_embedding
        ON chunks
        USING ivfflat (clip_embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )
    op.alter_column("chunks", "chunk_type", server_default=None)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunk_clip_embedding")
    op.drop_index("idx_chunk_type", table_name="chunks")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS clip_embedding")
    op.drop_column("chunks", "caption")
    op.drop_column("chunks", "image_key")
    op.drop_column("chunks", "bbox_y1")
    op.drop_column("chunks", "bbox_x1")
    op.drop_column("chunks", "bbox_y0")
    op.drop_column("chunks", "bbox_x0")
    op.drop_column("chunks", "chunk_type")
