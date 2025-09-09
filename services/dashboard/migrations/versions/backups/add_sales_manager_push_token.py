"""Add expo_push_token field to SalesManager model

Revision ID: add_sales_manager_push_token
Revises: 8fe77db67e22
Create Date: 2024-06-10 12:01:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_sales_manager_push_token'
down_revision: Union[str, None] = '8fe77db67e22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add expo_push_token column to sales_managers table
    op.add_column('sales_managers', sa.Column('expo_push_token', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove the column during downgrade
    op.drop_column('sales_managers', 'expo_push_token') 