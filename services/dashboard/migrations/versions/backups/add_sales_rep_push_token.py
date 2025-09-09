"""Add expo_push_token field to SalesRep model

Revision ID: add_sales_rep_push_token
Revises: create_transcript_analyses
Create Date: 2024-06-03 12:01:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_sales_rep_push_token'
down_revision: Union[str, None] = 'create_transcript_analyses'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add expo_push_token column to sales_reps table
    op.add_column('sales_reps', sa.Column('expo_push_token', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove the column during downgrade
    op.drop_column('sales_reps', 'expo_push_token') 