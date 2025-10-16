"""
Add AI data models for UWC integration.

Revision ID: 003_ai_models
Revises: 002_add_performance_indexes
Create Date: 2025-10-09 12:00:00.000000

This migration adds 7 new tables for AI features:
1. call_transcripts - ASR results storage
2. call_analysis - AI coaching and objection detection
3. rag_documents - Document tracking for knowledge base
4. rag_queries - Ask Otto query logs
5. followup_drafts - AI-generated follow-up messages
6. personal_clone_jobs - Voice clone training tracking
7. audit_logs - Security audit trail
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_ai_models'
down_revision = '002_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create AI data model tables."""
    
    # 1. Create call_transcripts table
    op.create_table(
        'call_transcripts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('uwc_job_id', sa.String(), nullable=False),
        sa.Column('transcript_text', sa.Text(), nullable=False),
        sa.Column('speaker_labels', sa.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('language', sa.String(), nullable=False, server_default='en-US'),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['call_id'], ['calls.call_id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for call_transcripts
    op.create_index('ix_transcripts_call_id', 'call_transcripts', ['call_id'])
    op.create_index('ix_transcripts_tenant_id', 'call_transcripts', ['tenant_id'])
    op.create_index('ix_transcripts_created_at', 'call_transcripts', ['created_at'])
    op.create_index('ix_transcripts_tenant_call', 'call_transcripts', ['tenant_id', 'call_id'])
    op.create_index('ix_transcripts_tenant_created', 'call_transcripts', ['tenant_id', 'created_at'])
    op.create_index('ix_transcripts_uwc_job', 'call_transcripts', ['uwc_job_id'], unique=True)
    
    # 2. Create call_analysis table
    op.create_table(
        'call_analysis',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('objections', sa.JSON(), nullable=True),
        sa.Column('objection_details', sa.JSON(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('coaching_tips', sa.JSON(), nullable=True),
        sa.Column('sop_stages_completed', sa.JSON(), nullable=True),
        sa.Column('sop_stages_missed', sa.JSON(), nullable=True),
        sa.Column('sop_compliance_score', sa.Float(), nullable=True),
        sa.Column('rehash_score', sa.Float(), nullable=True),
        sa.Column('talk_time_ratio', sa.Float(), nullable=True),
        sa.Column('lead_quality', sa.String(), nullable=True),
        sa.Column('conversion_probability', sa.Float(), nullable=True),
        sa.Column('meeting_segments', sa.JSON(), nullable=True),
        sa.Column('uwc_job_id', sa.String(), nullable=False),
        sa.Column('analyzed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('analysis_version', sa.String(), nullable=False, server_default='v1'),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['call_id'], ['calls.call_id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for call_analysis
    op.create_index('ix_analysis_call_id', 'call_analysis', ['call_id'])
    op.create_index('ix_analysis_tenant_id', 'call_analysis', ['tenant_id'])
    op.create_index('ix_analysis_created_at', 'call_analysis', ['created_at'])
    op.create_index('ix_analysis_tenant_call', 'call_analysis', ['tenant_id', 'call_id'])
    op.create_index('ix_analysis_uwc_job', 'call_analysis', ['uwc_job_id'], unique=True)
    op.create_index('ix_analysis_tenant_analyzed', 'call_analysis', ['tenant_id', 'analyzed_at'])
    op.create_index('ix_analysis_tenant_quality', 'call_analysis', ['tenant_id', 'lead_quality'])
    op.create_index('ix_analysis_tenant_rehash', 'call_analysis', ['tenant_id', 'rehash_score'])
    
    # 3. Create rag_documents table
    op.create_table(
        'rag_documents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('uploaded_by', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_url', sa.String(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(), nullable=True),
        sa.Column('document_type', sa.Enum('sop', 'script', 'objection_handler', 'product_info', 
                                           'training_material', 'policy', 'faq', 
                                           name='documenttype'), nullable=False),
        sa.Column('indexing_status', sa.Enum('pending', 'processing', 'indexed', 'failed', 'deleted',
                                             name='indexingstatus'), nullable=False, server_default='pending'),
        sa.Column('uwc_job_id', sa.String(), nullable=True),
        sa.Column('indexed_at', sa.DateTime(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for rag_documents
    op.create_index('ix_rag_docs_tenant_id', 'rag_documents', ['tenant_id'])
    op.create_index('ix_rag_docs_uploaded_by', 'rag_documents', ['uploaded_by'])
    op.create_index('ix_rag_docs_document_type', 'rag_documents', ['document_type'])
    op.create_index('ix_rag_docs_indexing_status', 'rag_documents', ['indexing_status'])
    op.create_index('ix_rag_docs_created_at', 'rag_documents', ['created_at'])
    op.create_index('ix_rag_docs_tenant', 'rag_documents', ['tenant_id'])
    op.create_index('ix_rag_docs_tenant_type', 'rag_documents', ['tenant_id', 'document_type'])
    op.create_index('ix_rag_docs_tenant_status', 'rag_documents', ['tenant_id', 'indexing_status'])
    op.create_index('ix_rag_docs_uwc_job', 'rag_documents', ['uwc_job_id'])
    op.create_index('ix_rag_docs_tenant_deleted', 'rag_documents', ['tenant_id', 'deleted'])
    
    # 4. Create rag_queries table
    op.create_table(
        'rag_queries',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('citations', sa.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('result_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('uwc_request_id', sa.String(), nullable=True),
        sa.Column('user_rating', sa.Integer(), nullable=True),
        sa.Column('user_feedback', sa.Text(), nullable=True),
        sa.Column('feedback_received_at', sa.DateTime(), nullable=True),
        sa.Column('user_role', sa.String(), nullable=True),
        sa.Column('query_context', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for rag_queries
    op.create_index('ix_rag_queries_tenant_id', 'rag_queries', ['tenant_id'])
    op.create_index('ix_rag_queries_user_id', 'rag_queries', ['user_id'])
    op.create_index('ix_rag_queries_created_at', 'rag_queries', ['created_at'])
    op.create_index('ix_rag_queries_tenant_user', 'rag_queries', ['tenant_id', 'user_id'])
    op.create_index('ix_rag_queries_tenant_created', 'rag_queries', ['tenant_id', 'created_at'])
    op.create_index('ix_rag_queries_user_created', 'rag_queries', ['user_id', 'created_at'])
    op.create_index('ix_rag_queries_tenant_role', 'rag_queries', ['tenant_id', 'user_role'])
    op.create_index('ix_rag_queries_tenant_rating', 'rag_queries', ['tenant_id', 'user_rating'])
    
    # 5. Create followup_drafts table
    op.create_table(
        'followup_drafts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('generated_for', sa.String(), nullable=False),
        sa.Column('generated_by', sa.String(), nullable=True),
        sa.Column('draft_text', sa.Text(), nullable=False),
        sa.Column('draft_type', sa.Enum('sms', 'email', 'call_script', name='drafttype'), nullable=False),
        sa.Column('tone', sa.String(), nullable=True),
        sa.Column('uwc_request_id', sa.String(), nullable=True),
        sa.Column('prompt_context', sa.JSON(), nullable=True),
        sa.Column('generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'sent', 'rejected', 'expired', 
                                    name='draftstatus'), nullable=False, server_default='pending'),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('modified_before_send', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('final_text', sa.Text(), nullable=True),
        sa.Column('blocked_by_quiet_hours', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('scheduled_send_time', sa.DateTime(), nullable=True),
        sa.Column('customer_responded', sa.Boolean(), nullable=True),
        sa.Column('customer_response_time_hours', sa.Integer(), nullable=True),
        sa.Column('led_to_booking', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['call_id'], ['calls.call_id'], ),
        sa.ForeignKeyConstraint(['generated_for'], ['users.id'], ),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for followup_drafts
    op.create_index('ix_drafts_tenant_id', 'followup_drafts', ['tenant_id'])
    op.create_index('ix_drafts_call_id', 'followup_drafts', ['call_id'])
    op.create_index('ix_drafts_generated_for', 'followup_drafts', ['generated_for'])
    op.create_index('ix_drafts_status', 'followup_drafts', ['status'])
    op.create_index('ix_drafts_created_at', 'followup_drafts', ['created_at'])
    op.create_index('ix_drafts_tenant_call', 'followup_drafts', ['tenant_id', 'call_id'])
    op.create_index('ix_drafts_tenant_user', 'followup_drafts', ['tenant_id', 'generated_for'])
    op.create_index('ix_drafts_tenant_status', 'followup_drafts', ['tenant_id', 'status'])
    op.create_index('ix_drafts_tenant_created', 'followup_drafts', ['tenant_id', 'created_at'])
    op.create_index('ix_drafts_user_pending', 'followup_drafts', ['generated_for', 'status'])
    op.create_index('ix_drafts_type_created', 'followup_drafts', ['draft_type', 'created_at'])
    
    # 6. Create personal_clone_jobs table
    op.create_table(
        'personal_clone_jobs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('rep_id', sa.String(), nullable=False),
        sa.Column('training_data_type', sa.Enum('calls', 'videos', 'transcripts', 'mixed', 
                                                name='trainingdatatype'), nullable=False),
        sa.Column('training_call_ids', sa.JSON(), nullable=True),
        sa.Column('training_media_urls', sa.JSON(), nullable=True),
        sa.Column('total_audio_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('total_media_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('uwc_job_id', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 
                                    name='trainingstatus'), nullable=False, server_default='pending'),
        sa.Column('progress_percent', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('current_epoch', sa.Integer(), nullable=True),
        sa.Column('total_epochs', sa.Integer(), nullable=True),
        sa.Column('loss', sa.Float(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('model_id', sa.String(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True),
        sa.Column('initiated_by', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['rep_id'], ['sales_reps.user_id'], ),
        sa.ForeignKeyConstraint(['initiated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for personal_clone_jobs
    op.create_index('ix_clone_jobs_tenant_id', 'personal_clone_jobs', ['tenant_id'])
    op.create_index('ix_clone_jobs_rep_id', 'personal_clone_jobs', ['rep_id'])
    op.create_index('ix_clone_jobs_status', 'personal_clone_jobs', ['status'])
    op.create_index('ix_clone_jobs_created_at', 'personal_clone_jobs', ['created_at'])
    op.create_index('ix_clone_jobs_tenant_rep', 'personal_clone_jobs', ['tenant_id', 'rep_id'])
    op.create_index('ix_clone_jobs_uwc_job', 'personal_clone_jobs', ['uwc_job_id'], unique=True)
    op.create_index('ix_clone_jobs_tenant_status', 'personal_clone_jobs', ['tenant_id', 'status'])
    op.create_index('ix_clone_jobs_rep_created', 'personal_clone_jobs', ['rep_id', 'created_at'])
    
    # 7. Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=False),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('success', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for audit_logs
    op.create_index('ix_audit_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_resource_type', 'audit_logs', ['resource_type'])
    op.create_index('ix_audit_resource_id', 'audit_logs', ['resource_id'])
    op.create_index('ix_audit_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_tenant_action', 'audit_logs', ['tenant_id', 'action'])
    op.create_index('ix_audit_tenant_created', 'audit_logs', ['tenant_id', 'created_at'])
    op.create_index('ix_audit_user_action', 'audit_logs', ['user_id', 'action'])
    op.create_index('ix_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('ix_audit_request', 'audit_logs', ['request_id'])


def downgrade() -> None:
    """Remove AI data model tables."""
    
    # Drop tables in reverse order (respect foreign keys)
    op.drop_table('audit_logs')
    op.drop_table('personal_clone_jobs')
    op.drop_table('followup_drafts')
    op.drop_table('rag_queries')
    op.drop_table('rag_documents')
    op.drop_table('call_analysis')
    op.drop_table('call_transcripts')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS trainingstatus')
    op.execute('DROP TYPE IF EXISTS trainingdatatype')
    op.execute('DROP TYPE IF EXISTS draftstatus')
    op.execute('DROP TYPE IF EXISTS drafttype')
    op.execute('DROP TYPE IF EXISTS indexingstatus')
    op.execute('DROP TYPE IF EXISTS documenttype')


