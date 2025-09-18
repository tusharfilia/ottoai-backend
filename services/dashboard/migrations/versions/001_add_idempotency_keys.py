"""Add idempotency_keys table

Revision ID: 001_add_idempotency_keys
Revises: 
Create Date: 2025-09-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_idempotency_keys'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create idempotency_keys table
    op.create_table('idempotency_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Text(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('external_id', sa.Text(), nullable=False),
        sa.Column('first_processed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_seen_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique constraint
    op.create_unique_constraint(
        'uq_idempotency_keys_tenant_provider_external',
        'idempotency_keys',
        ['tenant_id', 'provider', 'external_id']
    )
    
    # Create indexes
    op.create_index(
        'idx_idem_last_seen',
        'idempotency_keys',
        ['last_seen_at'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_idem_provider_tenant',
        'idempotency_keys',
        ['provider', 'tenant_id'],
        postgresql_using='btree'
    )


def downgrade():
    op.drop_index('idx_idem_provider_tenant', table_name='idempotency_keys')
    op.drop_index('idx_idem_last_seen', table_name='idempotency_keys')
    op.drop_constraint('uq_idempotency_keys_tenant_provider_external', 'idempotency_keys', type_='unique')
    op.drop_table('idempotency_keys')
