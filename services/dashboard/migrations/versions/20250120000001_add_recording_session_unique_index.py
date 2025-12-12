"""Add partial unique index for recording sessions

Revision ID: 20250120000001
Revises: 20250120000000
Create Date: 2025-01-20 00:00:00.000000

P0 FIX: Add partial unique index to prevent duplicate active recording sessions
for the same appointment. This is safe - it only prevents new duplicates, doesn't
affect existing data.

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250120000001'
down_revision = '20250120000000'
branch_labels = None
depends_on = None


def upgrade():
    # P0 FIX: Add partial unique index to prevent duplicate active sessions per appointment
    # This prevents race conditions where multiple start requests create duplicate sessions
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_recording_sessions_active_appointment 
        ON recording_sessions (appointment_id, company_id) 
        WHERE status IN ('pending', 'recording')
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_recording_sessions_active_appointment")



