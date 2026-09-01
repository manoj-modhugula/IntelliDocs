"""Add users table for authentication.

Revision ID: 002
Revises: 001
Create Date: 2026-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_verified', sa.Boolean(), default=False, nullable=False),
        sa.Column('default_workspace_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('api_calls_today', sa.String(20), default='0', nullable=False),
    )
    
    # Create indexes
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_is_active', 'users', ['is_active'])
    
    # Add user_id column to workspaces for ownership
    op.add_column('workspaces', sa.Column('user_id', sa.String(36), nullable=True))
    op.create_foreign_key('fk_workspaces_user', 'workspaces', 'users', ['user_id'], ['id'])
    
    # Add user_id column to documents for ownership
    op.add_column('documents', sa.Column('user_id', sa.String(36), nullable=True))
    op.create_foreign_key('fk_documents_user', 'documents', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    # Remove foreign keys
    op.drop_constraint('fk_documents_user', 'documents', type_='foreignkey')
    op.drop_column('documents', 'user_id')
    
    op.drop_constraint('fk_workspaces_user', 'workspaces', type_='foreignkey')
    op.drop_column('workspaces', 'user_id')
    
    # Drop indexes
    op.drop_index('ix_users_is_active', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    
    # Drop users table
    op.drop_table('users')
