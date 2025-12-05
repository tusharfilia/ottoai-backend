"""Add rep_shifts and recording_sessions tables

Revision ID: 20251115000000
Revises: 20251111000000
Create Date: 2025-11-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251115000000'
down_revision = '5a3b4c5d6e7f'  # This is the actual revision ID from 20251111000000_add_property_intelligence_fields.py
branch_labels = None
depends_on = None


def upgrade():
    # Create rep_shifts table
    op.create_table(
        'rep_shifts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('rep_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('clock_in_at', sa.DateTime(), nullable=True),
        sa.Column('clock_out_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_start', sa.Time(), nullable=True),
        sa.Column('scheduled_end', sa.Time(), nullable=True),
        sa.Column('status', sa.Enum('off', 'planned', 'active', 'completed', 'skipped', name='shift_status', native_enum=False), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['rep_id'], ['sales_reps.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rep_shifts_company_rep_date', 'rep_shifts', ['company_id', 'rep_id', 'shift_date'], unique=False)
    op.create_index(op.f('ix_rep_shifts_rep_id'), 'rep_shifts', ['rep_id'], unique=False)
    op.create_index(op.f('ix_rep_shifts_company_id'), 'rep_shifts', ['company_id'], unique=False)
    op.create_index(op.f('ix_rep_shifts_status'), 'rep_shifts', ['status'], unique=False)
    op.create_index(op.f('ix_rep_shifts_shift_date'), 'rep_shifts', ['shift_date'], unique=False)

    # Create recording_sessions table
    op.create_table(
        'recording_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('rep_id', sa.String(), nullable=False),
        sa.Column('appointment_id', sa.String(), nullable=False),
        sa.Column('shift_id', sa.String(), nullable=True),
        sa.Column('mode', sa.Enum('normal', 'ghost', 'off', name='recording_mode', native_enum=False), nullable=False),
        sa.Column('audio_storage_mode', sa.Enum('persistent', 'ephemeral', 'not_stored', name='audio_storage_mode', native_enum=False), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('start_lat', sa.Float(), nullable=True),
        sa.Column('start_lng', sa.Float(), nullable=True),
        sa.Column('end_lat', sa.Float(), nullable=True),
        sa.Column('end_lng', sa.Float(), nullable=True),
        sa.Column('geofence_radius_start', sa.Float(), nullable=True),
        sa.Column('geofence_radius_stop', sa.Float(), nullable=True),
        sa.Column('audio_url', sa.String(), nullable=True),
        sa.Column('audio_duration_seconds', sa.Float(), nullable=True),
        sa.Column('audio_size_bytes', sa.Integer(), nullable=True),
        sa.Column('transcription_status', sa.Enum('not_started', 'in_progress', 'completed', 'failed', name='transcription_status', native_enum=False), nullable=False),
        sa.Column('analysis_status', sa.Enum('not_started', 'in_progress', 'completed', 'failed', name='analysis_status', native_enum=False), nullable=False),
        sa.Column('shunya_asr_job_id', sa.String(), nullable=True),
        sa.Column('shunya_analysis_job_id', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['rep_id'], ['sales_reps.user_id'], ),
        sa.ForeignKeyConstraint(['shift_id'], ['rep_shifts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recording_sessions_company_rep_appointment', 'recording_sessions', ['company_id', 'rep_id', 'appointment_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_company_id'), 'recording_sessions', ['company_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_rep_id'), 'recording_sessions', ['rep_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_appointment_id'), 'recording_sessions', ['appointment_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_shift_id'), 'recording_sessions', ['shift_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_mode'), 'recording_sessions', ['mode'], unique=False)
    op.create_index(op.f('ix_recording_sessions_transcription_status'), 'recording_sessions', ['transcription_status'], unique=False)
    op.create_index(op.f('ix_recording_sessions_started_at'), 'recording_sessions', ['started_at'], unique=False)
    op.create_index(op.f('ix_recording_sessions_expires_at'), 'recording_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_recording_sessions_shunya_asr_job_id'), 'recording_sessions', ['shunya_asr_job_id'], unique=False)

    # Add columns to sales_reps table
    op.add_column('sales_reps', sa.Column('recording_mode', sa.Enum('normal', 'ghost', 'off', name='recording_mode', native_enum=False), nullable=False, server_default='normal'))
    op.add_column('sales_reps', sa.Column('allow_location_tracking', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('sales_reps', sa.Column('allow_recording', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('sales_reps', sa.Column('default_shift_start', sa.Time(), nullable=True))
    op.add_column('sales_reps', sa.Column('default_shift_end', sa.Time(), nullable=True))
    op.add_column('sales_reps', sa.Column('shift_config_source', sa.Enum('tenant_default', 'custom', name='shift_config_source', native_enum=False), nullable=False, server_default='tenant_default'))

    # Add columns to appointments table
    op.add_column('appointments', sa.Column('geo_lat', sa.Float(), nullable=True))
    op.add_column('appointments', sa.Column('geo_lng', sa.Float(), nullable=True))
    op.add_column('appointments', sa.Column('geofence_radius_start', sa.Float(), nullable=True, server_default='200.0'))
    op.add_column('appointments', sa.Column('geofence_radius_stop', sa.Float(), nullable=True, server_default='500.0'))


def downgrade():
    # Remove columns from appointments
    op.drop_column('appointments', 'geofence_radius_stop')
    op.drop_column('appointments', 'geofence_radius_start')
    op.drop_column('appointments', 'geo_lng')
    op.drop_column('appointments', 'geo_lat')

    # Remove columns from sales_reps
    op.drop_column('sales_reps', 'shift_config_source')
    op.drop_column('sales_reps', 'default_shift_end')
    op.drop_column('sales_reps', 'default_shift_start')
    op.drop_column('sales_reps', 'allow_recording')
    op.drop_column('sales_reps', 'allow_location_tracking')
    op.drop_column('sales_reps', 'recording_mode')

    # Drop recording_sessions table
    op.drop_index(op.f('ix_recording_sessions_shunya_asr_job_id'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_expires_at'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_started_at'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_transcription_status'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_mode'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_shift_id'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_appointment_id'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_rep_id'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_company_id'), table_name='recording_sessions')
    op.drop_index('ix_recording_sessions_company_rep_appointment', table_name='recording_sessions')
    op.drop_table('recording_sessions')

    # Drop rep_shifts table
    op.drop_index(op.f('ix_rep_shifts_shift_date'), table_name='rep_shifts')
    op.drop_index(op.f('ix_rep_shifts_status'), table_name='rep_shifts')
    op.drop_index(op.f('ix_rep_shifts_company_id'), table_name='rep_shifts')
    op.drop_index(op.f('ix_rep_shifts_rep_id'), table_name='rep_shifts')
    op.drop_index('ix_rep_shifts_company_rep_date', table_name='rep_shifts')
    op.drop_table('rep_shifts')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS shift_status")
    op.execute("DROP TYPE IF EXISTS recording_mode")
    op.execute("DROP TYPE IF EXISTS audio_storage_mode")
    op.execute("DROP TYPE IF EXISTS transcription_status")
    op.execute("DROP TYPE IF EXISTS analysis_status")
    op.execute("DROP TYPE IF EXISTS shift_config_source")

    
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251115000000'
down_revision = '5a3b4c5d6e7f'  # This is the actual revision ID from 20251111000000_add_property_intelligence_fields.py
branch_labels = None
depends_on = None


def upgrade():
    # Create rep_shifts table
    op.create_table(
        'rep_shifts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('rep_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('clock_in_at', sa.DateTime(), nullable=True),
        sa.Column('clock_out_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_start', sa.Time(), nullable=True),
        sa.Column('scheduled_end', sa.Time(), nullable=True),
        sa.Column('status', sa.Enum('off', 'planned', 'active', 'completed', 'skipped', name='shift_status', native_enum=False), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['rep_id'], ['sales_reps.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rep_shifts_company_rep_date', 'rep_shifts', ['company_id', 'rep_id', 'shift_date'], unique=False)
    op.create_index(op.f('ix_rep_shifts_rep_id'), 'rep_shifts', ['rep_id'], unique=False)
    op.create_index(op.f('ix_rep_shifts_company_id'), 'rep_shifts', ['company_id'], unique=False)
    op.create_index(op.f('ix_rep_shifts_status'), 'rep_shifts', ['status'], unique=False)
    op.create_index(op.f('ix_rep_shifts_shift_date'), 'rep_shifts', ['shift_date'], unique=False)

    # Create recording_sessions table
    op.create_table(
        'recording_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('rep_id', sa.String(), nullable=False),
        sa.Column('appointment_id', sa.String(), nullable=False),
        sa.Column('shift_id', sa.String(), nullable=True),
        sa.Column('mode', sa.Enum('normal', 'ghost', 'off', name='recording_mode', native_enum=False), nullable=False),
        sa.Column('audio_storage_mode', sa.Enum('persistent', 'ephemeral', 'not_stored', name='audio_storage_mode', native_enum=False), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('start_lat', sa.Float(), nullable=True),
        sa.Column('start_lng', sa.Float(), nullable=True),
        sa.Column('end_lat', sa.Float(), nullable=True),
        sa.Column('end_lng', sa.Float(), nullable=True),
        sa.Column('geofence_radius_start', sa.Float(), nullable=True),
        sa.Column('geofence_radius_stop', sa.Float(), nullable=True),
        sa.Column('audio_url', sa.String(), nullable=True),
        sa.Column('audio_duration_seconds', sa.Float(), nullable=True),
        sa.Column('audio_size_bytes', sa.Integer(), nullable=True),
        sa.Column('transcription_status', sa.Enum('not_started', 'in_progress', 'completed', 'failed', name='transcription_status', native_enum=False), nullable=False),
        sa.Column('analysis_status', sa.Enum('not_started', 'in_progress', 'completed', 'failed', name='analysis_status', native_enum=False), nullable=False),
        sa.Column('shunya_asr_job_id', sa.String(), nullable=True),
        sa.Column('shunya_analysis_job_id', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['rep_id'], ['sales_reps.user_id'], ),
        sa.ForeignKeyConstraint(['shift_id'], ['rep_shifts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_recording_sessions_company_rep_appointment', 'recording_sessions', ['company_id', 'rep_id', 'appointment_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_company_id'), 'recording_sessions', ['company_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_rep_id'), 'recording_sessions', ['rep_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_appointment_id'), 'recording_sessions', ['appointment_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_shift_id'), 'recording_sessions', ['shift_id'], unique=False)
    op.create_index(op.f('ix_recording_sessions_mode'), 'recording_sessions', ['mode'], unique=False)
    op.create_index(op.f('ix_recording_sessions_transcription_status'), 'recording_sessions', ['transcription_status'], unique=False)
    op.create_index(op.f('ix_recording_sessions_started_at'), 'recording_sessions', ['started_at'], unique=False)
    op.create_index(op.f('ix_recording_sessions_expires_at'), 'recording_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_recording_sessions_shunya_asr_job_id'), 'recording_sessions', ['shunya_asr_job_id'], unique=False)

    # Add columns to sales_reps table
    op.add_column('sales_reps', sa.Column('recording_mode', sa.Enum('normal', 'ghost', 'off', name='recording_mode', native_enum=False), nullable=False, server_default='normal'))
    op.add_column('sales_reps', sa.Column('allow_location_tracking', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('sales_reps', sa.Column('allow_recording', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('sales_reps', sa.Column('default_shift_start', sa.Time(), nullable=True))
    op.add_column('sales_reps', sa.Column('default_shift_end', sa.Time(), nullable=True))
    op.add_column('sales_reps', sa.Column('shift_config_source', sa.Enum('tenant_default', 'custom', name='shift_config_source', native_enum=False), nullable=False, server_default='tenant_default'))

    # Add columns to appointments table
    op.add_column('appointments', sa.Column('geo_lat', sa.Float(), nullable=True))
    op.add_column('appointments', sa.Column('geo_lng', sa.Float(), nullable=True))
    op.add_column('appointments', sa.Column('geofence_radius_start', sa.Float(), nullable=True, server_default='200.0'))
    op.add_column('appointments', sa.Column('geofence_radius_stop', sa.Float(), nullable=True, server_default='500.0'))


def downgrade():
    # Remove columns from appointments
    op.drop_column('appointments', 'geofence_radius_stop')
    op.drop_column('appointments', 'geofence_radius_start')
    op.drop_column('appointments', 'geo_lng')
    op.drop_column('appointments', 'geo_lat')

    # Remove columns from sales_reps
    op.drop_column('sales_reps', 'shift_config_source')
    op.drop_column('sales_reps', 'default_shift_end')
    op.drop_column('sales_reps', 'default_shift_start')
    op.drop_column('sales_reps', 'allow_recording')
    op.drop_column('sales_reps', 'allow_location_tracking')
    op.drop_column('sales_reps', 'recording_mode')

    # Drop recording_sessions table
    op.drop_index(op.f('ix_recording_sessions_shunya_asr_job_id'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_expires_at'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_started_at'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_transcription_status'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_mode'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_shift_id'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_appointment_id'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_rep_id'), table_name='recording_sessions')
    op.drop_index(op.f('ix_recording_sessions_company_id'), table_name='recording_sessions')
    op.drop_index('ix_recording_sessions_company_rep_appointment', table_name='recording_sessions')
    op.drop_table('recording_sessions')

    # Drop rep_shifts table
    op.drop_index(op.f('ix_rep_shifts_shift_date'), table_name='rep_shifts')
    op.drop_index(op.f('ix_rep_shifts_status'), table_name='rep_shifts')
    op.drop_index(op.f('ix_rep_shifts_company_id'), table_name='rep_shifts')
    op.drop_index(op.f('ix_rep_shifts_rep_id'), table_name='rep_shifts')
    op.drop_index('ix_rep_shifts_company_rep_date', table_name='rep_shifts')
    op.drop_table('rep_shifts')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS shift_status")
    op.execute("DROP TYPE IF EXISTS recording_mode")
    op.execute("DROP TYPE IF EXISTS audio_storage_mode")
    op.execute("DROP TYPE IF EXISTS transcription_status")
    op.execute("DROP TYPE IF EXISTS analysis_status")
    op.execute("DROP TYPE IF EXISTS shift_config_source")




