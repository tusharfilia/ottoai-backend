"""add_personal_otto_training_job

Revision ID: 20251208000002
Revises: 20251208000001
Create Date: 2025-12-08 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251208000002'
down_revision = '20251208000001'
branch_labels = None
depends_on = None


def upgrade():
    # Create personal_otto_training_jobs table
    op.create_table(
        'personal_otto_training_jobs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('rep_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('shunya_job_id', sa.String(), nullable=True),
        sa.Column('last_trained_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('job_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_personal_otto_company_rep', 'personal_otto_training_jobs', ['company_id', 'rep_id'])
    op.create_index('ix_personal_otto_status', 'personal_otto_training_jobs', ['company_id', 'status'])
    op.create_index('ix_personal_otto_shunya_job', 'personal_otto_training_jobs', ['shunya_job_id'])
    op.create_index(op.f('ix_personal_otto_training_jobs_company_id'), 'personal_otto_training_jobs', ['company_id'])
    op.create_index(op.f('ix_personal_otto_training_jobs_rep_id'), 'personal_otto_training_jobs', ['rep_id'])
    op.create_index(op.f('ix_personal_otto_training_jobs_created_at'), 'personal_otto_training_jobs', ['created_at'])


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_personal_otto_training_jobs_created_at'), table_name='personal_otto_training_jobs')
    op.drop_index(op.f('ix_personal_otto_training_jobs_rep_id'), table_name='personal_otto_training_jobs')
    op.drop_index(op.f('ix_personal_otto_training_jobs_company_id'), table_name='personal_otto_training_jobs')
    op.drop_index('ix_personal_otto_shunya_job', table_name='personal_otto_training_jobs')
    op.drop_index('ix_personal_otto_status', table_name='personal_otto_training_jobs')
    op.drop_index('ix_personal_otto_company_rep', table_name='personal_otto_training_jobs')
    
    # Drop table
    op.drop_table('personal_otto_training_jobs')

