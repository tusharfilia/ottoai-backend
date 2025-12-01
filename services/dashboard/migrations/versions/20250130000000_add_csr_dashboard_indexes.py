"""Add database indexes for CSR dashboard and high-read paths

Revision ID: 20250130000000
Revises: 20251115000000
Create Date: 2025-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '20250130000000'
down_revision = '20251115000000'  # Update this to match your latest migration
branch_labels = None
depends_on = None


def index_exists(bind, index_name: str) -> bool:
    """Check if an index exists in PostgreSQL."""
    dialect = bind.dialect.name
    if dialect == 'sqlite':
        # SQLite doesn't support IF NOT EXISTS in same way, use try/except
        return False
    result = bind.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = :index_name)"
        ),
        {"index_name": index_name}
    )
    return result.scalar()


def upgrade():
    """Add indexes for high-read paths used by CSR app and dashboards."""
    bind = op.get_bind()
    dialect = bind.dialect.name
    
    # ============================================
    # Appointment indexes
    # ============================================
    
    # Composite index for booking-rate queries: company_id + scheduled_start
    # Used by: GET /api/v1/dashboard/booking-rate
    # Query pattern: WHERE company_id = ? AND scheduled_start >= ? AND scheduled_start <= ?
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_appointments_company_id_scheduled_start'):
            op.create_index(
                'ix_appointments_company_id_scheduled_start',
                'appointments',
                ['company_id', 'scheduled_start'],
                unique=False
            )
    else:
        # SQLite or other - use try/except
        try:
            op.create_index(
                'ix_appointments_company_id_scheduled_start',
                'appointments',
                ['company_id', 'scheduled_start'],
                unique=False
            )
        except Exception:
            pass
    
    # Single column index for scheduled_start (if not already exists)
    # Used for date range queries on appointments
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_appointments_scheduled_start'):
            op.create_index(
                'ix_appointments_scheduled_start',
                'appointments',
                ['scheduled_start'],
                unique=False
            )
    else:
        try:
            op.create_index(
                'ix_appointments_scheduled_start',
                'appointments',
                ['scheduled_start'],
                unique=False
            )
        except Exception:
            pass
    
    # ============================================
    # Call indexes
    # ============================================
    
    # Composite index for dashboard queries: company_id + created_at
    # Used by: GET /api/v1/dashboard/calls, GET /api/v1/dashboard/metrics
    # Query pattern: WHERE company_id = ? AND created_at >= ? AND created_at <= ?
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_calls_company_id_created_at'):
            op.create_index(
                'ix_calls_company_id_created_at',
                'calls',
                ['company_id', 'created_at'],
                unique=False
            )
    else:
        try:
            op.create_index('ix_calls_company_id_created_at', 'calls', ['company_id', 'created_at'], unique=False)
        except Exception:
            pass
    
    # Single column index for company_id (if not already exists from FK)
    # Used for all tenant-scoped queries
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_calls_company_id'):
            op.create_index('ix_calls_company_id', 'calls', ['company_id'], unique=False)
    else:
        try:
            op.create_index('ix_calls_company_id', 'calls', ['company_id'], unique=False)
        except Exception:
            pass
    
    # Single column index for created_at
    # Used for time-series queries and sorting
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_calls_created_at'):
            op.create_index('ix_calls_created_at', 'calls', ['created_at'], unique=False)
    else:
        try:
            op.create_index('ix_calls_created_at', 'calls', ['created_at'], unique=False)
        except Exception:
            pass
    
    # Composite index for status filtering: company_id + status
    # Used by: GET /api/v1/dashboard/calls?status=...
    # Query pattern: WHERE company_id = ? AND status = ?
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_calls_company_id_status'):
            op.create_index('ix_calls_company_id_status', 'calls', ['company_id', 'status'], unique=False)
    else:
        try:
            op.create_index('ix_calls_company_id_status', 'calls', ['company_id', 'status'], unique=False)
        except Exception:
            pass
    
    # Composite index for rep-specific queries: assigned_rep_id + created_at
    # Used by: Rep performance queries, rep appointment lists
    # Query pattern: WHERE assigned_rep_id = ? AND created_at >= ?
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_calls_assigned_rep_id_created_at'):
            op.create_index('ix_calls_assigned_rep_id_created_at', 'calls', ['assigned_rep_id', 'created_at'], unique=False)
    else:
        try:
            op.create_index('ix_calls_assigned_rep_id_created_at', 'calls', ['assigned_rep_id', 'created_at'], unique=False)
        except Exception:
            pass
    
    # Composite index for booking analytics: company_id + booked
    # Used by: GET /api/v1/dashboard/metrics
    # Query pattern: WHERE company_id = ? AND booked = ?
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_calls_company_id_booked'):
            op.create_index('ix_calls_company_id_booked', 'calls', ['company_id', 'booked'], unique=False)
    else:
        try:
            op.create_index('ix_calls_company_id_booked', 'calls', ['company_id', 'booked'], unique=False)
        except Exception:
            pass
    
    # ============================================
    # MessageThread indexes
    # ============================================
    
    # Composite index for message thread queries: contact_card_id + created_at
    # Used by: GET /api/v1/message-threads/{contact_card_id}
    # Query pattern: WHERE contact_card_id = ? ORDER BY created_at ASC
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_message_threads_contact_card_id_created_at'):
            op.create_index(
                'ix_message_threads_contact_card_id_created_at',
                'message_threads',
                ['contact_card_id', 'created_at'],
                unique=False
            )
    else:
        try:
            op.create_index('ix_message_threads_contact_card_id_created_at', 'message_threads', ['contact_card_id', 'created_at'], unique=False)
        except Exception:
            pass
    
    # Note: contact_card_id and created_at already have single-column indexes
    # The composite index above is more efficient for the specific query pattern
    
    # ============================================
    # CallAnalysis indexes
    # ============================================
    
    # Composite index for top-objections queries: tenant_id + analyzed_at
    # Used by: GET /api/v1/dashboard/top-objections
    # Query pattern: WHERE tenant_id = ? AND analyzed_at >= ? AND analyzed_at <= ? AND objections IS NOT NULL
    # Note: Model already defines 'ix_analysis_tenant_analyzed' with same columns, but this ensures it exists
    # The index_exists check prevents duplicate creation
    if dialect == 'postgresql':
        if not index_exists(bind, 'ix_call_analysis_tenant_id_analyzed_at') and not index_exists(bind, 'ix_analysis_tenant_analyzed'):
            op.create_index(
                'ix_call_analysis_tenant_id_analyzed_at',
                'call_analysis',
                ['tenant_id', 'analyzed_at'],
                unique=False
            )
    else:
        try:
            op.create_index('ix_call_analysis_tenant_id_analyzed_at', 'call_analysis', ['tenant_id', 'analyzed_at'], unique=False)
        except Exception:
            pass


def downgrade():
    """Remove indexes added in upgrade."""
    
    # Remove Appointment indexes
    try:
        op.drop_index('ix_appointments_company_id_scheduled_start', 'appointments', if_exists=True)
    except Exception:
        pass
    
    try:
        op.drop_index('ix_appointments_scheduled_start', 'appointments', if_exists=True)
    except Exception:
        pass
    
    # Remove Call indexes
    try:
        op.drop_index('ix_calls_company_id_created_at', 'calls', if_exists=True)
    except Exception:
        pass
    
    try:
        op.drop_index('ix_calls_company_id', 'calls', if_exists=True)
    except Exception:
        pass
    
    try:
        op.drop_index('ix_calls_created_at', 'calls', if_exists=True)
    except Exception:
        pass
    
    try:
        op.drop_index('ix_calls_company_id_status', 'calls', if_exists=True)
    except Exception:
        pass
    
    try:
        op.drop_index('ix_calls_assigned_rep_id_created_at', 'calls', if_exists=True)
    except Exception:
        pass
    
    try:
        op.drop_index('ix_calls_company_id_booked', 'calls', if_exists=True)
    except Exception:
        pass
    
    # Remove MessageThread indexes
    try:
        op.drop_index('ix_message_threads_contact_card_id_created_at', 'message_threads', if_exists=True)
    except Exception:
        pass
    
    # Remove CallAnalysis indexes
    try:
        op.drop_index('ix_call_analysis_tenant_id_analyzed_at', 'call_analysis', if_exists=True)
    except Exception:
        pass

