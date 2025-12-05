"""recreate_all_tables

Revision ID: 8c79001578c0
Revises: 
Create Date: 2025-04-26T19:09:59.176773

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = '8c79001578c0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Use raw SQL to drop tables
    conn = op.get_bind()
    dialect = conn.dialect.name
    
    # SQLite doesn't support SET CONSTRAINTS or CASCADE
    # For SQLite, we just drop tables in reverse dependency order
    # For PostgreSQL, we can use CASCADE but skip SET CONSTRAINTS for compatibility
    
    # Drop all tables defined in the migration (in reverse dependency order)
    if dialect == 'sqlite':
        # SQLite: drop without CASCADE
        conn.execute(text('DROP TABLE IF EXISTS "users"'))
        conn.execute(text('DROP TABLE IF EXISTS "transcript_analyses"'))
        conn.execute(text('DROP TABLE IF EXISTS "services"'))
        conn.execute(text('DROP TABLE IF EXISTS "scheduled_calls"'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_reps"'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_managers"'))
        conn.execute(text('DROP TABLE IF EXISTS "companies"'))
        conn.execute(text('DROP TABLE IF EXISTS "calls"'))
    else:
        # PostgreSQL: use CASCADE
        conn.execute(text('DROP TABLE IF EXISTS "users" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "transcript_analyses" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "services" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "scheduled_calls" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_reps" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_managers" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "companies" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "calls" CASCADE'))

    # Create all tables in dependency order
    op.create_table(
        'calls',
        sa.Column('call_id', sa.Integer(), primary_key=True),
        sa.Column('missed_call', sa.Boolean(), server_default=sa.text('FALSE')),
        sa.Column('address', sa.String()),
        sa.Column('name', sa.String()),
        sa.Column('quote_date', sa.DateTime()),
        sa.Column('booked', sa.Boolean(), server_default=sa.text('FALSE')),
        sa.Column('phone_number', sa.String()),
        sa.Column('transcript', sa.String()),
        sa.Column('homeowner_followup_transcript', sa.String()),
        sa.Column('in_person_transcript', sa.Text()),
        sa.Column('mobile_transcript', sa.Text()),
        sa.Column('mobile_calls_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('mobile_texts_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('assigned_rep_id', sa.String()),
        sa.Column('bought', sa.Boolean(), server_default=sa.text('FALSE')),
        sa.Column('price_if_bought', sa.Float()),
        sa.Column('company_id', sa.String()),
        sa.Column('reason_for_lost_sale', sa.String()),
        sa.Column('reason_not_bought_homeowner', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('bland_call_id', sa.String()),
        sa.Column('homeowner_followup_call_id', sa.String()),
        sa.Column('transcript_discrepancies', sa.String()),
        sa.Column('problem', sa.String()),
        sa.Column('still_deciding', sa.Boolean(), server_default=sa.text('FALSE')),
        sa.Column('reason_for_deciding', sa.String()),
        sa.Column('cancelled', sa.Boolean(), server_default=sa.text('FALSE')),
        sa.Column('reason_for_cancellation', sa.String()),
        sa.Column('rescheduled', sa.Boolean(), server_default=sa.text('FALSE')),
        sa.Column('text_messages', sa.Text()),
        sa.Column('status', sa.String()),
        sa.Column('call_sid', sa.String()),
        sa.Column('last_call_status', sa.String()),
        sa.Column('last_call_timestamp', sa.String()),
        sa.Column('last_call_duration', sa.Integer()),
        sa.Column('geofence', sa.JSON()),
        sa.Column('geofence_entry_1_ts', sa.DateTime()),
        sa.Column('geofence_exit_1_ts', sa.DateTime()),
        sa.Column('geofence_time_1_m', sa.Integer()),
        sa.Column('geofence_entry_2_ts', sa.DateTime()),
        sa.Column('geofence_exit_2_ts', sa.DateTime()),
        sa.Column('geofence_time_2_m', sa.Integer()),
        sa.Column('geofence_multiple_entries', sa.Boolean(), server_default=sa.text('FALSE')),
        sa.Column('geofence_entry_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('recording_started_ts', sa.DateTime()),
        sa.Column('recording_stopped_ts', sa.DateTime()),
        sa.Column('recording_duration_s', sa.Integer()),
        sa.Column('time_to_start_recording_s', sa.Integer()),
        sa.Column('battery_at_geofence_entry', sa.Integer()),
        sa.Column('charging_at_geofence_entry', sa.Boolean()),
        sa.Column('battery_at_recording_start', sa.Integer()),
        sa.Column('charging_at_recording_start', sa.Boolean()),
    )

    op.create_table(
        'companies',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), unique=True),
        sa.Column('address', sa.String()),
        sa.Column('phone_number', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('callrail_api_key', sa.String()),
        sa.Column('callrail_account_id', sa.String()),
    )

    op.create_table(
        'sales_managers',
        sa.Column('user_id', sa.String()),
        sa.Column('company_id', sa.String()),
        sa.Column('expo_push_token', sa.String()),
    )

    op.create_table(
        'sales_reps',
        sa.Column('user_id', sa.String()),
        sa.Column('company_id', sa.String()),
        sa.Column('manager_id', sa.String()),
        sa.Column('active_geofences', sa.JSON()),
        sa.Column('expo_push_token', sa.String()),
    )

    op.create_table(
        'scheduled_calls',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('call_id', sa.String()),
        sa.Column('company_id', sa.String()),
        sa.Column('scheduled_time', sa.DateTime(), nullable=False),
        sa.Column('call_type', sa.String(), nullable=False),
        sa.Column('status', sa.String()),
        sa.Column('is_completed', sa.Boolean(), server_default=sa.text('FALSE')),
        sa.Column('bland_call_id', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'services',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), unique=True),
        sa.Column('description', sa.String()),
        sa.Column('base_price', sa.Float()),
        sa.Column('company_id', sa.Integer()),
    )

    op.create_table(
        'transcript_analyses',
        sa.Column('analysis_id', sa.Integer(), primary_key=True),
        sa.Column('call_id', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('greeting', sa.JSON()),
        sa.Column('customer_decision', sa.JSON()),
        sa.Column('quoted_price', sa.JSON()),
        sa.Column('company_mentions', sa.JSON()),
        sa.Column('farewell', sa.JSON()),
        sa.Column('rep_greeting_quote', sa.Text()),
        sa.Column('rep_greeting_timestamp', sa.String()),
        sa.Column('rep_introduction_quote', sa.Text()),
        sa.Column('rep_introduction_timestamp', sa.String()),
        sa.Column('company_mention_quote', sa.Text()),
        sa.Column('company_mention_timestamp', sa.String()),
        sa.Column('company_mention_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('price_quote', sa.Text()),
        sa.Column('price_quote_timestamp', sa.String()),
        sa.Column('price_amount', sa.String()),
        sa.Column('payment_discussion_quote', sa.Text()),
        sa.Column('payment_discussion_timestamp', sa.String()),
        sa.Column('discount_mention_quote', sa.Text()),
        sa.Column('discount_mention_timestamp', sa.String()),
        sa.Column('customer_decision_quote', sa.Text()),
        sa.Column('customer_decision_timestamp', sa.String()),
        sa.Column('customer_decision_status', sa.String()),
        sa.Column('agreement_mention_quote', sa.Text()),
        sa.Column('agreement_mention_timestamp', sa.String()),
        sa.Column('goodbye_quote', sa.Text()),
        sa.Column('goodbye_timestamp', sa.String()),
        sa.Column('follow_up_quote', sa.Text()),
        sa.Column('follow_up_timestamp', sa.String()),
        sa.Column('follow_up_date', sa.String()),
        sa.Column('document_sending_quote', sa.Text()),
        sa.Column('document_sending_timestamp', sa.String()),
        sa.Column('document_type', sa.String()),
        sa.Column('paperwork_mention_quote', sa.Text()),
        sa.Column('paperwork_mention_timestamp', sa.String()),
        sa.Column('raw_analysis', sa.JSON()),
        sa.Column('model_version', sa.String()),
        sa.Column('analysis_version', sa.Integer(), server_default=sa.text('1')),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(), unique=True),
        sa.Column('username', sa.String(), unique=True),
        sa.Column('name', sa.String()),
        sa.Column('phone_number', sa.String()),
        sa.Column('role', sa.String()),
        sa.Column('company_id', sa.String()),
    )

    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=True)
    op.create_index(op.f('ix_services_name'), 'services', ['name'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # SQLite doesn't support SET CONSTRAINTS, so skip for SQLite
    if dialect != 'sqlite':
        conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def downgrade():
    # Drop all tables
    conn = op.get_bind()
    dialect = conn.dialect.name
    
    # SQLite doesn't support SET CONSTRAINTS or CASCADE
    if dialect == 'sqlite':
        conn.execute(text('DROP TABLE IF EXISTS "calls"'))
        conn.execute(text('DROP TABLE IF EXISTS "companies"'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_managers"'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_reps"'))
        conn.execute(text('DROP TABLE IF EXISTS "scheduled_calls"'))
        conn.execute(text('DROP TABLE IF EXISTS "services"'))
        conn.execute(text('DROP TABLE IF EXISTS "transcript_analyses"'))
        conn.execute(text('DROP TABLE IF EXISTS "users"'))
    else:
        conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))
        conn.execute(text('DROP TABLE IF EXISTS "calls" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "companies" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_managers" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_reps" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "scheduled_calls" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "services" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "transcript_analyses" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "users" CASCADE'))
        conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))

    conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    conn.execute(text('DROP TABLE IF EXISTS "calls" CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS "companies" CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS "sales_managers" CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS "sales_reps" CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS "scheduled_calls" CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS "services" CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS "transcript_analyses" CASCADE'))
    conn.execute(text('DROP TABLE IF EXISTS "users" CASCADE'))
    conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def downgrade():
    # Drop all tables
    conn = op.get_bind()
    dialect = conn.dialect.name
    
    # SQLite doesn't support SET CONSTRAINTS or CASCADE
    if dialect == 'sqlite':
        conn.execute(text('DROP TABLE IF EXISTS "calls"'))
        conn.execute(text('DROP TABLE IF EXISTS "companies"'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_managers"'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_reps"'))
        conn.execute(text('DROP TABLE IF EXISTS "scheduled_calls"'))
        conn.execute(text('DROP TABLE IF EXISTS "services"'))
        conn.execute(text('DROP TABLE IF EXISTS "transcript_analyses"'))
        conn.execute(text('DROP TABLE IF EXISTS "users"'))
    else:
        conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))
        conn.execute(text('DROP TABLE IF EXISTS "calls" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "companies" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_managers" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "sales_reps" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "scheduled_calls" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "services" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "transcript_analyses" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "users" CASCADE'))
        conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))