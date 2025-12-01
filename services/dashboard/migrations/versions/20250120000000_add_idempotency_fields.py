"""Add idempotency fields for Shunya jobs, tasks, and key signals

Revision ID: 20250120000000
Revises: 20251115000000
Create Date: 2025-01-20 00:00:00.000000

This migration adds idempotency fields to prevent duplicate processing:
- tasks.unique_key: SHA256 hash of (source, description, contact_card_id)
- key_signals.unique_key: SHA256 hash of (signal_type, title, contact_card_id)
- shunya_jobs.processed_output_hash: SHA256 hash of processed output_payload

All fields are nullable to ensure backwards compatibility with existing rows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
# Note: If the migration chain is broken, you may need to adjust down_revision
# to match the actual head revision in your database
revision = '20250120000000'
down_revision = '20251115000000'  # Latest migration before this one
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (idempotency check)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index exists (idempotency check)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    """Add idempotency fields to tasks, key_signals, and shunya_jobs tables."""
    
    # 1. Add unique_key to tasks table
    if not column_exists('tasks', 'unique_key'):
        op.add_column(
            'tasks',
            sa.Column('unique_key', sa.String(), nullable=True, comment='Hash of (source, description, contact_card_id) for duplicate detection')
        )
        print("Added unique_key column to tasks table")
    else:
        print("unique_key column already exists in tasks table, skipping")
    
    # Create index on tasks.unique_key (idempotent)
    if not index_exists('tasks', 'ix_tasks_unique_key'):
        op.create_index(
            'ix_tasks_unique_key',
            'tasks',
            ['unique_key', 'company_id'],
            unique=False
        )
        print("Created index ix_tasks_unique_key on tasks table")
    else:
        print("Index ix_tasks_unique_key already exists on tasks table, skipping")
    
    # 2. Add unique_key to key_signals table
    if not column_exists('key_signals', 'unique_key'):
        op.add_column(
            'key_signals',
            sa.Column('unique_key', sa.String(), nullable=True, comment='Hash of (signal_type, title, contact_card_id) for duplicate detection')
        )
        print("Added unique_key column to key_signals table")
    else:
        print("unique_key column already exists in key_signals table, skipping")
    
    # Create index on key_signals.unique_key (idempotent)
    if not index_exists('key_signals', 'ix_signals_unique_key'):
        op.create_index(
            'ix_signals_unique_key',
            'key_signals',
            ['unique_key', 'company_id'],
            unique=False
        )
        print("Created index ix_signals_unique_key on key_signals table")
    else:
        print("Index ix_signals_unique_key already exists on key_signals table, skipping")
    
    # 3. Add processed_output_hash to shunya_jobs table (if table exists)
    # Check if table exists first (in case migration runs before shunya_jobs table is created)
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    
    if 'shunya_jobs' in tables:
        if not column_exists('shunya_jobs', 'processed_output_hash'):
            op.add_column(
                'shunya_jobs',
                sa.Column('processed_output_hash', sa.String(), nullable=True, index=True, comment='SHA256 hash of output_payload for idempotency')
            )
            print("Added processed_output_hash column to shunya_jobs table")
        else:
            print("processed_output_hash column already exists in shunya_jobs table, skipping")
        
        # Create index on shunya_jobs.processed_output_hash (idempotent)
        # Note: The column already has index=True, but we verify the index exists
        if not index_exists('shunya_jobs', 'ix_shunya_jobs_processed_output_hash'):
            op.create_index(
                'ix_shunya_jobs_processed_output_hash',
                'shunya_jobs',
                ['processed_output_hash'],
                unique=False
            )
            print("Created index ix_shunya_jobs_processed_output_hash on shunya_jobs table")
        else:
            print("Index ix_shunya_jobs_processed_output_hash already exists on shunya_jobs table, skipping")
    else:
        print("shunya_jobs table does not exist yet, skipping processed_output_hash column addition")


def downgrade():
    """Remove idempotency fields."""
    
    # Remove indexes first
    if index_exists('shunya_jobs', 'ix_shunya_jobs_processed_output_hash'):
        op.drop_index('ix_shunya_jobs_processed_output_hash', table_name='shunya_jobs')
    
    if index_exists('key_signals', 'ix_signals_unique_key'):
        op.drop_index('ix_signals_unique_key', table_name='key_signals')
    
    if index_exists('tasks', 'ix_tasks_unique_key'):
        op.drop_index('ix_tasks_unique_key', table_name='tasks')
    
    # Remove columns
    if column_exists('shunya_jobs', 'processed_output_hash'):
        op.drop_column('shunya_jobs', 'processed_output_hash')
    
    if column_exists('key_signals', 'unique_key'):
        op.drop_column('key_signals', 'unique_key')
    
    if column_exists('tasks', 'unique_key'):
        op.drop_column('tasks', 'unique_key')


Revision ID: 20250120000000
Revises: 20251115000000
Create Date: 2025-01-20 00:00:00.000000

This migration adds idempotency fields to prevent duplicate processing:
- tasks.unique_key: SHA256 hash of (source, description, contact_card_id)
- key_signals.unique_key: SHA256 hash of (signal_type, title, contact_card_id)
- shunya_jobs.processed_output_hash: SHA256 hash of processed output_payload

All fields are nullable to ensure backwards compatibility with existing rows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
# Note: If the migration chain is broken, you may need to adjust down_revision
# to match the actual head revision in your database
revision = '20250120000000'
down_revision = '20251115000000'  # Latest migration before this one
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (idempotency check)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index exists (idempotency check)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    """Add idempotency fields to tasks, key_signals, and shunya_jobs tables."""
    
    # 1. Add unique_key to tasks table
    if not column_exists('tasks', 'unique_key'):
        op.add_column(
            'tasks',
            sa.Column('unique_key', sa.String(), nullable=True, comment='Hash of (source, description, contact_card_id) for duplicate detection')
        )
        print("Added unique_key column to tasks table")
    else:
        print("unique_key column already exists in tasks table, skipping")
    
    # Create index on tasks.unique_key (idempotent)
    if not index_exists('tasks', 'ix_tasks_unique_key'):
        op.create_index(
            'ix_tasks_unique_key',
            'tasks',
            ['unique_key', 'company_id'],
            unique=False
        )
        print("Created index ix_tasks_unique_key on tasks table")
    else:
        print("Index ix_tasks_unique_key already exists on tasks table, skipping")
    
    # 2. Add unique_key to key_signals table
    if not column_exists('key_signals', 'unique_key'):
        op.add_column(
            'key_signals',
            sa.Column('unique_key', sa.String(), nullable=True, comment='Hash of (signal_type, title, contact_card_id) for duplicate detection')
        )
        print("Added unique_key column to key_signals table")
    else:
        print("unique_key column already exists in key_signals table, skipping")
    
    # Create index on key_signals.unique_key (idempotent)
    if not index_exists('key_signals', 'ix_signals_unique_key'):
        op.create_index(
            'ix_signals_unique_key',
            'key_signals',
            ['unique_key', 'company_id'],
            unique=False
        )
        print("Created index ix_signals_unique_key on key_signals table")
    else:
        print("Index ix_signals_unique_key already exists on key_signals table, skipping")
    
    # 3. Add processed_output_hash to shunya_jobs table (if table exists)
    # Check if table exists first (in case migration runs before shunya_jobs table is created)
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    
    if 'shunya_jobs' in tables:
        if not column_exists('shunya_jobs', 'processed_output_hash'):
            op.add_column(
                'shunya_jobs',
                sa.Column('processed_output_hash', sa.String(), nullable=True, index=True, comment='SHA256 hash of output_payload for idempotency')
            )
            print("Added processed_output_hash column to shunya_jobs table")
        else:
            print("processed_output_hash column already exists in shunya_jobs table, skipping")
        
        # Create index on shunya_jobs.processed_output_hash (idempotent)
        # Note: The column already has index=True, but we verify the index exists
        if not index_exists('shunya_jobs', 'ix_shunya_jobs_processed_output_hash'):
            op.create_index(
                'ix_shunya_jobs_processed_output_hash',
                'shunya_jobs',
                ['processed_output_hash'],
                unique=False
            )
            print("Created index ix_shunya_jobs_processed_output_hash on shunya_jobs table")
        else:
            print("Index ix_shunya_jobs_processed_output_hash already exists on shunya_jobs table, skipping")
    else:
        print("shunya_jobs table does not exist yet, skipping processed_output_hash column addition")


def downgrade():
    """Remove idempotency fields."""
    
    # Remove indexes first
    if index_exists('shunya_jobs', 'ix_shunya_jobs_processed_output_hash'):
        op.drop_index('ix_shunya_jobs_processed_output_hash', table_name='shunya_jobs')
    
    if index_exists('key_signals', 'ix_signals_unique_key'):
        op.drop_index('ix_signals_unique_key', table_name='key_signals')
    
    if index_exists('tasks', 'ix_tasks_unique_key'):
        op.drop_index('ix_tasks_unique_key', table_name='tasks')
    
    # Remove columns
    if column_exists('shunya_jobs', 'processed_output_hash'):
        op.drop_column('shunya_jobs', 'processed_output_hash')
    
    if column_exists('key_signals', 'unique_key'):
        op.drop_column('key_signals', 'unique_key')
    
    if column_exists('tasks', 'unique_key'):
        op.drop_column('tasks', 'unique_key')


Revision ID: 20250120000000
Revises: 20251115000000
Create Date: 2025-01-20 00:00:00.000000

This migration adds idempotency fields to prevent duplicate processing:
- tasks.unique_key: SHA256 hash of (source, description, contact_card_id)
- key_signals.unique_key: SHA256 hash of (signal_type, title, contact_card_id)
- shunya_jobs.processed_output_hash: SHA256 hash of processed output_payload

All fields are nullable to ensure backwards compatibility with existing rows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
# Note: If the migration chain is broken, you may need to adjust down_revision
# to match the actual head revision in your database
revision = '20250120000000'
down_revision = '20251115000000'  # Latest migration before this one
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table (idempotency check)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index exists (idempotency check)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade():
    """Add idempotency fields to tasks, key_signals, and shunya_jobs tables."""
    
    # 1. Add unique_key to tasks table
    if not column_exists('tasks', 'unique_key'):
        op.add_column(
            'tasks',
            sa.Column('unique_key', sa.String(), nullable=True, comment='Hash of (source, description, contact_card_id) for duplicate detection')
        )
        print("Added unique_key column to tasks table")
    else:
        print("unique_key column already exists in tasks table, skipping")
    
    # Create index on tasks.unique_key (idempotent)
    if not index_exists('tasks', 'ix_tasks_unique_key'):
        op.create_index(
            'ix_tasks_unique_key',
            'tasks',
            ['unique_key', 'company_id'],
            unique=False
        )
        print("Created index ix_tasks_unique_key on tasks table")
    else:
        print("Index ix_tasks_unique_key already exists on tasks table, skipping")
    
    # 2. Add unique_key to key_signals table
    if not column_exists('key_signals', 'unique_key'):
        op.add_column(
            'key_signals',
            sa.Column('unique_key', sa.String(), nullable=True, comment='Hash of (signal_type, title, contact_card_id) for duplicate detection')
        )
        print("Added unique_key column to key_signals table")
    else:
        print("unique_key column already exists in key_signals table, skipping")
    
    # Create index on key_signals.unique_key (idempotent)
    if not index_exists('key_signals', 'ix_signals_unique_key'):
        op.create_index(
            'ix_signals_unique_key',
            'key_signals',
            ['unique_key', 'company_id'],
            unique=False
        )
        print("Created index ix_signals_unique_key on key_signals table")
    else:
        print("Index ix_signals_unique_key already exists on key_signals table, skipping")
    
    # 3. Add processed_output_hash to shunya_jobs table (if table exists)
    # Check if table exists first (in case migration runs before shunya_jobs table is created)
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    
    if 'shunya_jobs' in tables:
        if not column_exists('shunya_jobs', 'processed_output_hash'):
            op.add_column(
                'shunya_jobs',
                sa.Column('processed_output_hash', sa.String(), nullable=True, index=True, comment='SHA256 hash of output_payload for idempotency')
            )
            print("Added processed_output_hash column to shunya_jobs table")
        else:
            print("processed_output_hash column already exists in shunya_jobs table, skipping")
        
        # Create index on shunya_jobs.processed_output_hash (idempotent)
        # Note: The column already has index=True, but we verify the index exists
        if not index_exists('shunya_jobs', 'ix_shunya_jobs_processed_output_hash'):
            op.create_index(
                'ix_shunya_jobs_processed_output_hash',
                'shunya_jobs',
                ['processed_output_hash'],
                unique=False
            )
            print("Created index ix_shunya_jobs_processed_output_hash on shunya_jobs table")
        else:
            print("Index ix_shunya_jobs_processed_output_hash already exists on shunya_jobs table, skipping")
    else:
        print("shunya_jobs table does not exist yet, skipping processed_output_hash column addition")


def downgrade():
    """Remove idempotency fields."""
    
    # Remove indexes first
    if index_exists('shunya_jobs', 'ix_shunya_jobs_processed_output_hash'):
        op.drop_index('ix_shunya_jobs_processed_output_hash', table_name='shunya_jobs')
    
    if index_exists('key_signals', 'ix_signals_unique_key'):
        op.drop_index('ix_signals_unique_key', table_name='key_signals')
    
    if index_exists('tasks', 'ix_tasks_unique_key'):
        op.drop_index('ix_tasks_unique_key', table_name='tasks')
    
    # Remove columns
    if column_exists('shunya_jobs', 'processed_output_hash'):
        op.drop_column('shunya_jobs', 'processed_output_hash')
    
    if column_exists('key_signals', 'unique_key'):
        op.drop_column('key_signals', 'unique_key')
    
    if column_exists('tasks', 'unique_key'):
        op.drop_column('tasks', 'unique_key')

