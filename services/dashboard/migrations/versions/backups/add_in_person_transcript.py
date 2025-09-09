"""Add in_person_transcript to Call model

Revision ID: add_in_person_transcript
Revises: initial_migration
Create Date: 2024-05-14 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_in_person_transcript'
down_revision: Union[str, None] = 'initial_migration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add in_person_transcript column to calls table
    op.add_column('calls', sa.Column('in_person_transcript', sa.Text(), nullable=True))
    op.add_column('calls', sa.Column('has_in_person_transcript', sa.Boolean(), server_default='false', nullable=False))
    
    # Update the updated_at column to include onupdate
    op.execute('ALTER TABLE calls ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()')
    op.execute('ALTER TABLE calls ALTER COLUMN updated_at SET DEFAULT NOW()')
    
    # Add appointment_id column if it doesn't exist
    op.add_column('calls', sa.Column('appointment_id', sa.String(), nullable=True))
    
    # Add has_transcript column if it doesn't exist
    op.add_column('calls', sa.Column('has_transcript', sa.Boolean(), server_default='false', nullable=False))
    
    # Add status column if it doesn't exist
    op.add_column('calls', sa.Column('status', sa.String(), server_default='pending', nullable=True))


def downgrade() -> None:
    # Remove the columns added in upgrade
    op.drop_column('calls', 'in_person_transcript')
    op.drop_column('calls', 'has_in_person_transcript')
    
    # Only drop the columns we added in this migration
    op.drop_column('calls', 'appointment_id')
    op.drop_column('calls', 'has_transcript')
    op.drop_column('calls', 'status') 