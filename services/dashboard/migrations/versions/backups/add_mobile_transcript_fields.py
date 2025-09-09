"""Add mobile transcript, call count, and text count fields to Call model

Revision ID: add_mobile_transcript_fields
Revises: efbcc30cbcfc
Create Date: 2024-05-28 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_mobile_transcript_fields'
down_revision: Union[str, None] = 'efbcc30cbcfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add mobile_transcript column to calls table
    op.add_column('calls', sa.Column('mobile_transcript', sa.Text(), nullable=True))
    
    # Add mobile call and text counters
    op.add_column('calls', sa.Column('mobile_calls_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('calls', sa.Column('mobile_texts_count', sa.Integer(), server_default='0', nullable=False))
    
    # Add call_sid column if it doesn't exist
    op.add_column('calls', sa.Column('call_sid', sa.String(), nullable=True))
    
    # Add call status fields
    op.add_column('calls', sa.Column('last_call_status', sa.String(), nullable=True))
    op.add_column('calls', sa.Column('last_call_timestamp', sa.String(), nullable=True))
    op.add_column('calls', sa.Column('last_call_duration', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove the columns added in upgrade
    op.drop_column('calls', 'mobile_transcript')
    op.drop_column('calls', 'mobile_calls_count')
    op.drop_column('calls', 'mobile_texts_count')
    op.drop_column('calls', 'call_sid')
    op.drop_column('calls', 'last_call_status')
    op.drop_column('calls', 'last_call_timestamp')
    op.drop_column('calls', 'last_call_duration') 