"""Add document versioning fields.

Revision ID: 20260203_006
Revises: 20260202_005
Create Date: 2026-02-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260203_006"
down_revision: Union[str, None] = "20260202_005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "documents",
        sa.Column(
            "previous_document_id",
            sa.String(36),
            sa.ForeignKey("documents.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_document_version",
        "documents",
        ["version"],
    )


def downgrade() -> None:
    op.drop_index("idx_document_version", table_name="documents")
    op.drop_column("documents", "previous_document_id")
    op.drop_column("documents", "version")
