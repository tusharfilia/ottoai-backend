"""Add onboarding tables and fields

Revision ID: 20251201000000
Revises: 20251115000000
Create Date: 2025-12-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251201000000'
down_revision = '20251115000000'  # Update this to match your latest migration
branch_labels = None
depends_on = None


def upgrade():
    # Add onboarding fields to companies table
    op.add_column('companies', sa.Column('industry', sa.String(), nullable=True))
    op.add_column('companies', sa.Column('timezone', sa.String(), nullable=True, server_default='America/New_York'))
    op.add_column('companies', sa.Column('domain', sa.String(), nullable=True))
    op.add_column('companies', sa.Column('domain_verified', sa.Boolean(), nullable=False, server_default='false'))
    
    # Add call provider enum and fields
    call_provider_enum = sa.Enum('callrail', 'twilio', name='call_provider', native_enum=False)
    call_provider_enum.create(op.get_bind(), checkfirst=True)
    
    op.add_column('companies', sa.Column('call_provider', call_provider_enum, nullable=True))
    op.add_column('companies', sa.Column('twilio_account_sid', sa.String(), nullable=True))
    op.add_column('companies', sa.Column('twilio_auth_token', sa.String(), nullable=True))
    op.add_column('companies', sa.Column('primary_tracking_number', sa.String(), nullable=True))
    
    # Add onboarding progress fields
    op.add_column('companies', sa.Column('onboarding_step', sa.String(), nullable=False, server_default='company_basics'))
    op.add_column('companies', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('companies', sa.Column('onboarding_completed_at', sa.DateTime(), nullable=True))
    
    # Add subscription fields
    op.add_column('companies', sa.Column('subscription_status', sa.String(), nullable=False, server_default='trialing'))
    op.add_column('companies', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))
    op.add_column('companies', sa.Column('max_seats', sa.Integer(), nullable=False, server_default='5'))
    
    # Add fields to users table
    op.add_column('users', sa.Column('territory', sa.String(), nullable=True))
    op.add_column('users', sa.Column('preferences_json', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    
    # Create documents table
    document_category_enum = sa.Enum('sop', 'training', 'reference', 'policy', name='document_category', native_enum=False)
    document_category_enum.create(op.get_bind(), checkfirst=True)
    
    ingestion_status_enum = sa.Enum('pending', 'processing', 'done', 'failed', name='ingestion_status', native_enum=False)
    ingestion_status_enum.create(op.get_bind(), checkfirst=True)
    
    op.create_table(
        'documents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('category', document_category_enum, nullable=False),
        sa.Column('role_target', sa.String(), nullable=True),
        sa.Column('s3_url', sa.String(), nullable=False),
        sa.Column('ingestion_job_id', sa.String(), nullable=True),
        sa.Column('ingestion_status', ingestion_status_enum, nullable=False, server_default='pending'),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_company_id'), 'documents', ['company_id'], unique=False)
    
    # Create onboarding_events table
    op.create_table(
        'onboarding_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('step', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_onboarding_events_company_id'), 'onboarding_events', ['company_id'], unique=False)
    op.create_index(op.f('ix_onboarding_events_timestamp'), 'onboarding_events', ['timestamp'], unique=False)


def downgrade():
    # Drop onboarding_events table
    op.drop_index(op.f('ix_onboarding_events_timestamp'), table_name='onboarding_events')
    op.drop_index(op.f('ix_onboarding_events_company_id'), table_name='onboarding_events')
    op.drop_table('onboarding_events')
    
    # Drop documents table
    op.drop_index(op.f('ix_documents_company_id'), table_name='documents')
    op.drop_table('documents')
    
    # Drop enums
    sa.Enum(name='ingestion_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='document_category').drop(op.get_bind(), checkfirst=True)
    
    # Remove fields from users table
    op.drop_column('users', 'preferences_json')
    op.drop_column('users', 'territory')
    
    # Remove fields from companies table
    op.drop_column('companies', 'max_seats')
    op.drop_column('companies', 'trial_ends_at')
    op.drop_column('companies', 'subscription_status')
    op.drop_column('companies', 'onboarding_completed_at')
    op.drop_column('companies', 'onboarding_completed')
    op.drop_column('companies', 'onboarding_step')
    op.drop_column('companies', 'primary_tracking_number')
    op.drop_column('companies', 'twilio_auth_token')
    op.drop_column('companies', 'twilio_account_sid')
    op.drop_column('companies', 'call_provider')
    op.drop_column('companies', 'domain_verified')
    op.drop_column('companies', 'domain')
    op.drop_column('companies', 'timezone')
    op.drop_column('companies', 'industry')
    
    # Drop call_provider enum
    sa.Enum(name='call_provider').drop(op.get_bind(), checkfirst=True)

