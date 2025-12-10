"""add_followup_recommendations_to_call_analysis

Revision ID: 20251208000000
Revises: 20251201000000
Create Date: 2025-12-08 13:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251208000000'
down_revision = '20251201000000'
branch_labels = None
depends_on = None


def upgrade():
    # Add followup_recommendations JSON column to call_analysis table
    op.add_column(
        'call_analysis',
        sa.Column('followup_recommendations', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade():
    # Remove followup_recommendations column
    op.drop_column('call_analysis', 'followup_recommendations')

