"""Add performance indexes for tenant-scoped queries

Revision ID: 002_add_performance_indexes
Revises: 001_add_idempotency_keys
Create Date: 2025-09-22 13:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_add_performance_indexes'
down_revision = '001_add_idempotency_keys'
branch_labels = None
depends_on = None

def upgrade():
    """Add performance indexes for tenant-scoped queries."""
    
    # Add indexes for calls table (if it exists)
    try:
        op.create_index('ix_calls_tenant_created_at', 'calls', ['tenant_id', 'created_at'])
        op.create_index('ix_calls_tenant_status', 'calls', ['tenant_id', 'status'])
    except Exception:
        # Table might not exist yet
        pass
    
    # Add indexes for followups table (if it exists)
    try:
        op.create_index('ix_followups_tenant_created_at', 'followups', ['tenant_id', 'created_at'])
        op.create_index('ix_followups_tenant_status', 'followups', ['tenant_id', 'status'])
    except Exception:
        # Table might not exist yet
        pass
    
    # Add indexes for messages table (if it exists)
    try:
        op.create_index('ix_messages_tenant_created_at', 'messages', ['tenant_id', 'created_at'])
        op.create_index('ix_messages_tenant_status', 'messages', ['tenant_id', 'status'])
    except Exception:
        # Table might not exist yet
        pass
    
    # Add indexes for leads/contacts table (if it exists)
    try:
        op.create_index('ix_leads_tenant_phone', 'leads', ['tenant_id', 'phone'])
        op.create_index('ix_contacts_tenant_phone', 'contacts', ['tenant_id', 'phone'])
    except Exception:
        # Table might not exist yet
        pass
    
    # Add indexes for appointments table (if it exists)
    try:
        op.create_index('ix_appointments_tenant_created_at', 'appointments', ['tenant_id', 'created_at'])
        op.create_index('ix_appointments_tenant_status', 'appointments', ['tenant_id', 'status'])
    except Exception:
        # Table might not exist yet
        pass

def downgrade():
    """Remove performance indexes."""
    
    # Remove indexes for calls table
    try:
        op.drop_index('ix_calls_tenant_created_at', 'calls')
        op.drop_index('ix_calls_tenant_status', 'calls')
    except Exception:
        pass
    
    # Remove indexes for followups table
    try:
        op.drop_index('ix_followups_tenant_created_at', 'followups')
        op.drop_index('ix_followups_tenant_status', 'followups')
    except Exception:
        pass
    
    # Remove indexes for messages table
    try:
        op.drop_index('ix_messages_tenant_created_at', 'messages')
        op.drop_index('ix_messages_tenant_status', 'messages')
    except Exception:
        pass
    
    # Remove indexes for leads/contacts table
    try:
        op.drop_index('ix_leads_tenant_phone', 'leads')
        op.drop_index('ix_contacts_tenant_phone', 'contacts')
    except Exception:
        pass
    
    # Remove indexes for appointments table
    try:
        op.drop_index('ix_appointments_tenant_created_at', 'appointments')
        op.drop_index('ix_appointments_tenant_status', 'appointments')
    except Exception:
        pass
