"""Remove unused fields from calls table

Revision ID: 8fe77db67e22
Revises: add_sales_rep_push_token
Create Date: 2023-08-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8fe77db67e22'
down_revision = 'add_sales_rep_push_token'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop columns that are no longer used in the Call model
    op.drop_column('calls', 'escalated')
    op.drop_column('calls', 'escalation_addressed')
    op.drop_column('calls', 'sales_rep_followup_call_id')
    op.drop_column('calls', 'sales_call_transcript')


def downgrade() -> None:
    # Add back columns that were removed
    op.add_column('calls', sa.Column('escalated', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('calls', sa.Column('escalation_addressed', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('calls', sa.Column('sales_rep_followup_call_id', sa.String(), nullable=True))
    op.add_column('calls', sa.Column('sales_call_transcript', sa.String(), nullable=True)) 