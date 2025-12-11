"""Add recording session status field

Revision ID: c93a1d60ca61
Revises: 8168aa9bda7a
Create Date: 2025-12-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c93a1d60ca61'
down_revision = '8168aa9bda7a'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Add status column to recording_sessions table
    if not column_exists('recording_sessions', 'status'):
        op.add_column(
            'recording_sessions',
            sa.Column(
                'status',
                sa.String(),
                nullable=False,
                server_default='pending',
                comment='Session status: pending, recording, completed, failed'
            )
        )
        op.create_index(op.f('ix_recording_sessions_status'), 'recording_sessions', ['status'], unique=False)


def downgrade():
    # Drop status column
    if column_exists('recording_sessions', 'status'):
        op.drop_index(op.f('ix_recording_sessions_status'), table_name='recording_sessions')
        op.drop_column('recording_sessions', 'status')
