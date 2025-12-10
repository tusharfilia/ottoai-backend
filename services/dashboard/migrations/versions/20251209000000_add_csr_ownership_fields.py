"""Add CSR ownership fields to Call and Task models

Revision ID: 20251209000000
Revises: 20251208000003
Create Date: 2025-12-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251209000000'
down_revision = '20251208000003'
branch_labels = None
depends_on = None


def upgrade():
    # Add owner_id to calls table (CSR who handled the call)
    op.add_column('calls', sa.Column('owner_id', sa.String(), nullable=True, comment='User ID of the CSR who handled this call'))
    op.create_index(op.f('ix_calls_owner_id'), 'calls', ['owner_id'], unique=False)
    
    # Add assignee_id to tasks table (specific user assigned to task)
    op.add_column('tasks', sa.Column('assignee_id', sa.String(), nullable=True, comment='User ID of the specific user assigned to this task'))
    op.create_index(op.f('ix_tasks_assignee_id'), 'tasks', ['assignee_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_tasks_assignee_id'), table_name='tasks')
    op.drop_column('tasks', 'assignee_id')
    op.drop_index(op.f('ix_calls_owner_id'), table_name='calls')
    op.drop_column('calls', 'owner_id')

