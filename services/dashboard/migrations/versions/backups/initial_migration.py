"""Initial migration

Revision ID: initial_migration
Revises: 
Create Date: 2024-03-21 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'initial_migration'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create companies table
    op.create_table(
        'companies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('callrail_api_key', sa.String(), nullable=True),
        sa.Column('callrail_account_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )

    # Create sales_managers table
    op.create_table(
        'sales_managers',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id')
    )

    # Create sales_reps table
    op.create_table(
        'sales_reps',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('manager_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['manager_id'], ['sales_managers.user_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id')
    )

    # Create services table
    op.create_table(
        'services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('base_price', sa.Float(), nullable=True),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create calls table
    op.create_table(
        'calls',
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('missed_call', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('quote_date', sa.DateTime(), nullable=True),
        sa.Column('booked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('transcript', sa.String(), nullable=True),
        sa.Column('sales_call_transcript', sa.String(), nullable=True),
        sa.Column('homeowner_followup_transcript', sa.String(), nullable=True),
        sa.Column('assigned_rep_id', sa.String(), nullable=True),
        sa.Column('escalated', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('escalation_addressed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('bought', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('price_if_bought', sa.Float(), nullable=True),
        sa.Column('company_id', sa.String(), nullable=True),
        sa.Column('reason_for_lost_sale', sa.String(), nullable=True),
        sa.Column('reason_not_bought_homeowner', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('bland_call_id', sa.String(), nullable=True),
        sa.Column('sales_rep_followup_call_id', sa.String(), nullable=True),
        sa.Column('homeowner_followup_call_id', sa.String(), nullable=True),
        sa.Column('transcript_discrepancies', sa.String(), nullable=True),
        sa.Column('problem', sa.String(), nullable=True),
        sa.Column('still_deciding', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reason_for_deciding', sa.String(), nullable=True),
        sa.Column('cancelled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('reason_for_cancellation', sa.String(), nullable=True),
        sa.Column('rescheduled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('text_messages', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_rep_id'], ['sales_reps.user_id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('call_id')
    )

    # Create scheduled_calls table
    op.create_table(
        'scheduled_calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(), nullable=False),
        sa.Column('call_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='pending', nullable=False),
        sa.Column('is_completed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('bland_call_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['call_id'], ['calls.call_id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop all tables in reverse order to handle foreign key constraints
    op.drop_table('scheduled_calls')
    op.drop_table('calls')
    op.drop_table('services')
    op.drop_table('sales_reps')
    op.drop_table('sales_managers')
    op.drop_table('users')
    op.drop_table('companies') 