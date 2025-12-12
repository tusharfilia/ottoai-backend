"""add_canonical_enums_to_models

Revision ID: 20251208000003
Revises: 20251208000002
Create Date: 2025-12-08 16:00:00.000000

Add canonical enum fields aligned with Shunya's enums-inventory-by-service.md:
- booking_status, call_type, call_outcome_category to call_analysis
- action_type to tasks
- call_type to calls
- appointment_type to appointments

All fields are nullable for backward compatibility.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251208000003'
down_revision = '20251208000002'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Add booking_status, call_type, call_outcome_category to call_analysis
    if not column_exists('call_analysis', 'booking_status'):
        op.add_column(
            'call_analysis',
            sa.Column('booking_status', sa.String(), nullable=True, comment='Canonical booking status: booked, not_booked, service_not_offered')
        )
    if not column_exists('call_analysis', 'call_type'):
        op.add_column(
            'call_analysis',
            sa.Column('call_type', sa.String(), nullable=True, comment='Canonical call type: sales_call, csr_call')
        )
    if not column_exists('call_analysis', 'call_outcome_category'):
        op.add_column(
            'call_analysis',
            sa.Column('call_outcome_category', sa.String(), nullable=True, comment='Computed from qualification_status + booking_status')
        )
    
    # Add action_type to tasks
    if not column_exists('tasks', 'action_type'):
        op.add_column(
            'tasks',
            sa.Column('action_type', sa.String(), nullable=True, comment='Canonical action type: call_back, send_quote, schedule_appointment, etc. (30 values)')
        )
    
    # Add call_type to calls
    if not column_exists('calls', 'call_type'):
        op.add_column(
            'calls',
            sa.Column('call_type', sa.String(), nullable=True, comment='Canonical call type: sales_call, csr_call')
        )
    
    # Add appointment_type to appointments
    if not column_exists('appointments', 'appointment_type'):
        op.add_column(
            'appointments',
            sa.Column('appointment_type', sa.String(), nullable=True, comment='Canonical appointment type: in-person, virtual, phone')
        )


def downgrade():
    # Remove enum columns (safe - all are nullable)
    if column_exists('call_analysis', 'call_outcome_category'):
        op.drop_column('call_analysis', 'call_outcome_category')
    if column_exists('call_analysis', 'call_type'):
        op.drop_column('call_analysis', 'call_type')
    if column_exists('call_analysis', 'booking_status'):
        op.drop_column('call_analysis', 'booking_status')
    
    if column_exists('tasks', 'action_type'):
        op.drop_column('tasks', 'action_type')
    
    if column_exists('calls', 'call_type'):
        op.drop_column('calls', 'call_type')
    
    if column_exists('appointments', 'appointment_type'):
        op.drop_column('appointments', 'appointment_type')



