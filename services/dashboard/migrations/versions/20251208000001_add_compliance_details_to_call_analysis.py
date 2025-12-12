"""add_compliance_details_to_call_analysis

Revision ID: 20251208000001
Revises: 20251208000000
Create Date: 2025-12-08 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251208000001'
down_revision = '20251208000000'
branch_labels = None
depends_on = None


def upgrade():
    # Add compliance detail fields to call_analysis table
    op.add_column(
        'call_analysis',
        sa.Column('compliance_violations', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'call_analysis',
        sa.Column('compliance_positive_behaviors', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        'call_analysis',
        sa.Column('compliance_recommendations', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )


def downgrade():
    # Remove compliance detail columns
    op.drop_column('call_analysis', 'compliance_recommendations')
    op.drop_column('call_analysis', 'compliance_positive_behaviors')
    op.drop_column('call_analysis', 'compliance_violations')



