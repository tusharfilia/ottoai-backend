"""add geofence tracking

Revision ID: add_geofence_tracking
Revises: add_mobile_transcript_fields
Create Date: 2024-04-11 08:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_geofence_tracking'
down_revision = 'add_mobile_transcript_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns to calls table
    op.add_column('calls', sa.Column('geofence', JSONB, nullable=True))
    op.add_column('calls', sa.Column('geofence_entry_1_ts', sa.DateTime(), nullable=True))
    op.add_column('calls', sa.Column('geofence_exit_1_ts', sa.DateTime(), nullable=True))
    op.add_column('calls', sa.Column('geofence_time_1_m', sa.Integer(), nullable=True))
    op.add_column('calls', sa.Column('geofence_entry_2_ts', sa.DateTime(), nullable=True))
    op.add_column('calls', sa.Column('geofence_exit_2_ts', sa.DateTime(), nullable=True))
    op.add_column('calls', sa.Column('geofence_time_2_m', sa.Integer(), nullable=True))
    op.add_column('calls', sa.Column('geofence_multiple_entries', sa.Boolean(), server_default='false'))
    op.add_column('calls', sa.Column('geofence_entry_count', sa.Integer(), server_default='0'))
    op.add_column('calls', sa.Column('recording_started_ts', sa.DateTime(), nullable=True))
    op.add_column('calls', sa.Column('recording_stopped_ts', sa.DateTime(), nullable=True))
    op.add_column('calls', sa.Column('recording_duration_s', sa.Integer(), nullable=True))
    op.add_column('calls', sa.Column('time_to_start_recording_s', sa.Integer(), nullable=True))
    op.add_column('calls', sa.Column('battery_at_geofence_entry', sa.Integer(), nullable=True))
    op.add_column('calls', sa.Column('charging_at_geofence_entry', sa.Boolean(), nullable=True))
    op.add_column('calls', sa.Column('battery_at_recording_start', sa.Integer(), nullable=True))
    op.add_column('calls', sa.Column('charging_at_recording_start', sa.Boolean(), nullable=True))

    # Add column to sales_reps table
    op.add_column('sales_reps', sa.Column('active_geofences', JSONB, nullable=True))


def downgrade():
    # Remove columns from calls table
    op.drop_column('calls', 'geofence')
    op.drop_column('calls', 'geofence_entry_1_ts')
    op.drop_column('calls', 'geofence_exit_1_ts')
    op.drop_column('calls', 'geofence_time_1_m')
    op.drop_column('calls', 'geofence_entry_2_ts')
    op.drop_column('calls', 'geofence_exit_2_ts')
    op.drop_column('calls', 'geofence_time_2_m')
    op.drop_column('calls', 'geofence_multiple_entries')
    op.drop_column('calls', 'geofence_entry_count')
    op.drop_column('calls', 'recording_started_ts')
    op.drop_column('calls', 'recording_stopped_ts')
    op.drop_column('calls', 'recording_duration_s')
    op.drop_column('calls', 'time_to_start_recording_s')
    op.drop_column('calls', 'battery_at_geofence_entry')
    op.drop_column('calls', 'charging_at_geofence_entry')
    op.drop_column('calls', 'battery_at_recording_start')
    op.drop_column('calls', 'charging_at_recording_start')

    # Remove column from sales_reps table
    op.drop_column('sales_reps', 'active_geofences') 