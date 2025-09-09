"""Create transcript_analyses table

Revision ID: create_transcript_analyses
Revises: add_geofence_tracking
Create Date: 2024-06-25 14:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'create_transcript_analyses'
down_revision: Union[str, None] = 'add_geofence_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create transcript_analyses table
    op.create_table(
        'transcript_analyses',
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('call_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        # Analysis data fields
        sa.Column('greeting', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('customer_decision', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('quoted_price', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('company_mentions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('farewell', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Specific information fields with actual quotes and timestamps
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
        
        # Raw analysis result
        sa.Column('raw_analysis', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Metadata
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('analysis_version', sa.Integer(), nullable=True),
        
        # Primary key and foreign key
        sa.PrimaryKeyConstraint('analysis_id'),
        sa.ForeignKeyConstraint(['call_id'], ['calls.call_id'], ),
        sa.Index('ix_transcript_analyses_analysis_id', 'analysis_id')
    )
    
    # Create index on call_id for faster lookups
    op.create_index('ix_transcript_analyses_call_id', 'transcript_analyses', ['call_id'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_transcript_analyses_call_id', table_name='transcript_analyses')
    op.drop_index('ix_transcript_analyses_analysis_id', table_name='transcript_analyses')
    
    # Drop the table
    op.drop_table('transcript_analyses') 