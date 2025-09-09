"""recreate_all_tables_manually

Revision ID: 3e87b46d526e
Revises: add_sales_manager_push_token
Create Date: 2025-04-22 23:49:44.505167

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3e87b46d526e'
down_revision: Union[str, None] = 'add_sales_manager_push_token'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Don't drop alembic_version, we'll handle it manually
    # Drop all existing tables except alembic_version
    op.execute('DROP TABLE IF EXISTS calls CASCADE')
    op.execute('DROP TABLE IF EXISTS sales_reps CASCADE')
    op.execute('DROP TABLE IF EXISTS sales_managers CASCADE')
    op.execute('DROP TABLE IF EXISTS services CASCADE')
    op.execute('DROP TABLE IF EXISTS scheduled_calls CASCADE')
    op.execute('DROP TABLE IF EXISTS companies CASCADE')
    op.execute('DROP TABLE IF EXISTS users CASCADE')
    op.execute('DROP TABLE IF EXISTS transcript_analyses CASCADE')
    
    # Create alembic_version table if it doesn't exist, but don't modify it
    # Alembic itself will handle updating the version as part of its normal process
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'alembic_version' not in inspector.get_table_names():
        op.create_table(
            'alembic_version',
            sa.Column('version_num', sa.String(32), nullable=False),
            sa.PrimaryKeyConstraint('version_num')
        )
        # Insert the previous version so Alembic can update it to the current one
        op.execute("INSERT INTO alembic_version (version_num) VALUES ('add_sales_manager_push_token')")

    # Create companies table
    op.create_table('companies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('callrail_api_key', sa.String(), nullable=True),
        sa.Column('callrail_account_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=True)

    # Create users table
    op.create_table('users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=True),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # Create services table
    op.create_table('services',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('company_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create sales_managers table with all columns
    op.create_table('sales_managers',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('expo_push_token', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id')
    )

    # Create sales_reps table - fixed to exactly match model
    op.create_table('sales_reps',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('manager_id', sa.String(), nullable=True),
        sa.Column('active_geofences', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('expo_push_token', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['manager_id'], ['sales_managers.user_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id')
    )

    # Create calls table
    op.create_table('calls',
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('missed_call', sa.Boolean(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('quote_date', sa.DateTime(), nullable=True),
        sa.Column('booked', sa.Boolean(), nullable=True),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('transcript', sa.String(), nullable=True),
        sa.Column('homeowner_followup_transcript', sa.String(), nullable=True),
        sa.Column('in_person_transcript', sa.Text(), nullable=True),
        sa.Column('mobile_transcript', sa.Text(), nullable=True),
        sa.Column('mobile_calls_count', sa.Integer(), nullable=True),
        sa.Column('mobile_texts_count', sa.Integer(), nullable=True),
        sa.Column('assigned_rep_id', sa.String(), nullable=True),
        sa.Column('bought', sa.Boolean(), nullable=True),
        sa.Column('price_if_bought', sa.Float(), nullable=True),
        sa.Column('company_id', sa.String(), nullable=True),
        sa.Column('reason_for_lost_sale', sa.String(), nullable=True),
        sa.Column('reason_not_bought_homeowner', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('bland_call_id', sa.String(), nullable=True),
        sa.Column('homeowner_followup_call_id', sa.String(), nullable=True),
        sa.Column('transcript_discrepancies', sa.String(), nullable=True),
        sa.Column('problem', sa.String(), nullable=True),
        sa.Column('still_deciding', sa.Boolean(), nullable=True),
        sa.Column('reason_for_deciding', sa.String(), nullable=True),
        sa.Column('cancelled', sa.Boolean(), nullable=True),
        sa.Column('reason_for_cancellation', sa.String(), nullable=True),
        sa.Column('rescheduled', sa.Boolean(), nullable=True),
        sa.Column('text_messages', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('call_sid', sa.String(), nullable=True),
        sa.Column('last_call_status', sa.String(), nullable=True),
        sa.Column('last_call_timestamp', sa.String(), nullable=True),
        sa.Column('last_call_duration', sa.Integer(), nullable=True),
        sa.Column('geofence', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('geofence_entry_1_ts', sa.DateTime(), nullable=True),
        sa.Column('geofence_exit_1_ts', sa.DateTime(), nullable=True),
        sa.Column('geofence_time_1_m', sa.Integer(), nullable=True),
        sa.Column('geofence_entry_2_ts', sa.DateTime(), nullable=True),
        sa.Column('geofence_exit_2_ts', sa.DateTime(), nullable=True),
        sa.Column('geofence_time_2_m', sa.Integer(), nullable=True),
        sa.Column('geofence_multiple_entries', sa.Boolean(), nullable=True),
        sa.Column('geofence_entry_count', sa.Integer(), nullable=True),
        sa.Column('recording_started_ts', sa.DateTime(), nullable=True),
        sa.Column('recording_stopped_ts', sa.DateTime(), nullable=True),
        sa.Column('recording_duration_s', sa.Integer(), nullable=True),
        sa.Column('time_to_start_recording_s', sa.Integer(), nullable=True),
        sa.Column('battery_at_geofence_entry', sa.Integer(), nullable=True),
        sa.Column('charging_at_geofence_entry', sa.Boolean(), nullable=True),
        sa.Column('battery_at_recording_start', sa.Integer(), nullable=True),
        sa.Column('charging_at_recording_start', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_rep_id'], ['sales_reps.user_id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('call_id')
    )
    op.create_index(op.f('ix_calls_call_id'), 'calls', ['call_id'], unique=False)

    # Create scheduled_calls table
    op.create_table('scheduled_calls',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=True),
        sa.Column('scheduled_time', sa.DateTime(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=True),
        sa.Column('call_id', sa.String(), nullable=True),
        sa.Column('rep_id', sa.String(), nullable=True),
        sa.Column('company_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['rep_id'], ['sales_reps.user_id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create transcript_analyses table with exactly the 41 columns listed
    op.create_table('transcript_analyses',
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        # Detailed analysis data
        sa.Column('greeting', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('customer_decision', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('quoted_price', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('company_mentions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('farewell', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Specific information fields
        sa.Column('rep_greeting_quote', sa.Text(), nullable=True),
        sa.Column('rep_greeting_timestamp', sa.String(), nullable=True),
        sa.Column('rep_introduction_quote', sa.Text(), nullable=True),
        sa.Column('rep_introduction_timestamp', sa.String(), nullable=True),
        sa.Column('company_mention_quote', sa.Text(), nullable=True),
        sa.Column('company_mention_timestamp', sa.String(), nullable=True),
        sa.Column('company_mention_count', sa.Integer(), nullable=True),
        sa.Column('price_quote', sa.Text(), nullable=True),
        sa.Column('price_quote_timestamp', sa.String(), nullable=True),
        sa.Column('price_amount', sa.String(), nullable=True),
        sa.Column('payment_discussion_quote', sa.Text(), nullable=True),
        sa.Column('payment_discussion_timestamp', sa.String(), nullable=True),
        sa.Column('discount_mention_quote', sa.Text(), nullable=True),
        sa.Column('discount_mention_timestamp', sa.String(), nullable=True),
        sa.Column('customer_decision_quote', sa.Text(), nullable=True),
        sa.Column('customer_decision_timestamp', sa.String(), nullable=True),
        sa.Column('customer_decision_status', sa.String(), nullable=True),
        sa.Column('agreement_mention_quote', sa.Text(), nullable=True),
        sa.Column('agreement_mention_timestamp', sa.String(), nullable=True),
        sa.Column('goodbye_quote', sa.Text(), nullable=True),
        sa.Column('goodbye_timestamp', sa.String(), nullable=True),
        sa.Column('follow_up_quote', sa.Text(), nullable=True),
        sa.Column('follow_up_timestamp', sa.String(), nullable=True),
        sa.Column('follow_up_date', sa.String(), nullable=True),
        sa.Column('document_sending_quote', sa.Text(), nullable=True),
        sa.Column('document_sending_timestamp', sa.String(), nullable=True),
        sa.Column('document_type', sa.String(), nullable=True),
        sa.Column('paperwork_mention_quote', sa.Text(), nullable=True),
        sa.Column('paperwork_mention_timestamp', sa.String(), nullable=True),
        
        # Raw analysis and metadata
        sa.Column('raw_analysis', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('analysis_version', sa.Integer(), nullable=True),
        
        sa.ForeignKeyConstraint(['call_id'], ['calls.call_id'], ),
        sa.PrimaryKeyConstraint('analysis_id')
    )
    op.create_index(op.f('ix_transcript_analyses_analysis_id'), 'transcript_analyses', ['analysis_id'], unique=False)


def downgrade() -> None:
    # We don't want to drop tables on downgrade since we're recreating the database
    pass
