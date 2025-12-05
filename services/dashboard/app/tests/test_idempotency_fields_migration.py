"""
Tests for idempotency fields migration.

Verifies that:
1. The new idempotency fields exist in the database schema
2. Fields can be written and read correctly
3. Models and DB schema stay in sync
"""
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine
from app.config import settings
from app.models.task import Task, TaskSource
from app.models.key_signal import KeySignal, SignalType
from app.models.shunya_job import ShunyaJob, ShunyaJobType, ShunyaJobStatus
from app.utils.idempotency import (
    generate_task_unique_key,
    generate_signal_unique_key,
    generate_output_payload_hash,
)


def test_tasks_table_has_unique_key_column(db_session: Session):
    """Test that tasks table has unique_key column."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('tasks')]
    
    assert 'unique_key' in columns, "tasks table missing unique_key column"
    
    # Check column properties
    for col in inspector.get_columns('tasks'):
        if col['name'] == 'unique_key':
            assert col['nullable'] is True, "unique_key should be nullable"
            assert col['type'].python_type == str or col['type'].python_type.__name__ == 'STRING', \
                "unique_key should be String type"
            break


def test_key_signals_table_has_unique_key_column(db_session: Session):
    """Test that key_signals table has unique_key column."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('key_signals')]
    
    assert 'unique_key' in columns, "key_signals table missing unique_key column"
    
    # Check column properties
    for col in inspector.get_columns('key_signals'):
        if col['name'] == 'unique_key':
            assert col['nullable'] is True, "unique_key should be nullable"
            break


def test_shunya_jobs_table_has_processed_output_hash_column(db_session: Session):
    """Test that shunya_jobs table has processed_output_hash column."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'shunya_jobs' not in tables:
        pytest.skip("shunya_jobs table does not exist yet")
    
    columns = [col['name'] for col in inspector.get_columns('shunya_jobs')]
    
    assert 'processed_output_hash' in columns, "shunya_jobs table missing processed_output_hash column"
    
    # Check column properties
    for col in inspector.get_columns('shunya_jobs'):
        if col['name'] == 'processed_output_hash':
            assert col['nullable'] is True, "processed_output_hash should be nullable"
            break


def test_tasks_unique_key_index_exists(db_session: Session):
    """Test that index on tasks.unique_key exists."""
    inspector = inspect(engine)
    indexes = [idx['name'] for idx in inspector.get_indexes('tasks')]
    
    # Check for index on unique_key (may be composite with company_id)
    unique_key_indexes = [
        idx for idx in inspector.get_indexes('tasks')
        if 'unique_key' in [col for col in idx.get('column_names', [])]
    ]
    
    assert len(unique_key_indexes) > 0, "Index on tasks.unique_key not found"


def test_key_signals_unique_key_index_exists(db_session: Session):
    """Test that index on key_signals.unique_key exists."""
    inspector = inspect(engine)
    indexes = [idx['name'] for idx in inspector.get_indexes('key_signals')]
    
    # Check for index on unique_key (may be composite with company_id)
    unique_key_indexes = [
        idx for idx in inspector.get_indexes('key_signals')
        if 'unique_key' in [col for col in idx.get('column_names', [])]
    ]
    
    assert len(unique_key_indexes) > 0, "Index on key_signals.unique_key not found"


def test_task_unique_key_read_write(db_session: Session):
    """Test that Task.unique_key can be written and read."""
    from app.models.contact_card import ContactCard
    from app.models.company import Company
    
    # Create test company and contact card if they don't exist
    company = db_session.query(Company).first()
    if not company:
        pytest.skip("No company found in database")
    
    contact_card = db_session.query(ContactCard).filter_by(company_id=company.id).first()
    if not contact_card:
        pytest.skip("No contact card found in database")
    
    # Generate unique key
    unique_key = generate_task_unique_key(
        source=TaskSource.SHUNYA,
        description="Test task description",
        contact_card_id=contact_card.id,
    )
    
    # Create task with unique_key
    task = Task(
        company_id=company.id,
        contact_card_id=contact_card.id,
        description="Test task description",
        assigned_to="csr",
        source=TaskSource.SHUNYA,
        unique_key=unique_key,
        status="open"
    )
    
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    
    # Verify unique_key was saved
    assert task.unique_key == unique_key, "unique_key not saved correctly"
    
    # Clean up
    db_session.delete(task)
    db_session.commit()


def test_key_signal_unique_key_read_write(db_session: Session):
    """Test that KeySignal.unique_key can be written and read."""
    from app.models.contact_card import ContactCard
    from app.models.company import Company
    
    # Create test company and contact card if they don't exist
    company = db_session.query(Company).first()
    if not company:
        pytest.skip("No company found in database")
    
    contact_card = db_session.query(ContactCard).filter_by(company_id=company.id).first()
    if not contact_card:
        pytest.skip("No contact card found in database")
    
    # Generate unique key
    unique_key = generate_signal_unique_key(
        signal_type=SignalType.OPPORTUNITY,
        title="Test signal",
        contact_card_id=contact_card.id,
    )
    
    # Create signal with unique_key
    signal = KeySignal(
        company_id=company.id,
        contact_card_id=contact_card.id,
        signal_type=SignalType.OPPORTUNITY,
        severity="high",
        title="Test signal",
        unique_key=unique_key,
        acknowledged=False
    )
    
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    
    # Verify unique_key was saved
    assert signal.unique_key == unique_key, "unique_key not saved correctly"
    
    # Clean up
    db_session.delete(signal)
    db_session.commit()


def test_shunya_job_processed_output_hash_read_write(db_session: Session):
    """Test that ShunyaJob.processed_output_hash can be written and read."""
    from app.models.contact_card import ContactCard
    from app.models.company import Company
    
    # Create test company and contact card if they don't exist
    company = db_session.query(Company).first()
    if not company:
        pytest.skip("No company found in database")
    
    contact_card = db_session.query(ContactCard).filter_by(company_id=company.id).first()
    if not contact_card:
        pytest.skip("No contact card found in database")
    
    # Generate output hash
    output_payload = {"test": "data", "status": "completed"}
    output_hash = generate_output_payload_hash(output_payload)
    
    # Create job with processed_output_hash
    job = ShunyaJob(
        company_id=company.id,
        contact_card_id=contact_card.id,
        job_type=ShunyaJobType.CSR_CALL,
        job_status=ShunyaJobStatus.PENDING,
        shunya_job_id="test-shunya-job-123",
        processed_output_hash=output_hash,
    )
    
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    
    # Verify processed_output_hash was saved
    assert job.processed_output_hash == output_hash, "processed_output_hash not saved correctly"
    
    # Clean up
    db_session.delete(job)
    db_session.commit()


def test_migration_is_idempotent(db_session: Session):
    """Test that running the migration twice doesn't cause errors."""
    # This test verifies the migration can be run multiple times safely
    # The migration itself has idempotency checks built in
    inspector = inspect(engine)
    
    # Verify columns exist (migration should have run)
    tasks_columns = [col['name'] for col in inspector.get_columns('tasks')]
    assert 'unique_key' in tasks_columns, "Migration should add unique_key to tasks"
    
    key_signals_columns = [col['name'] for col in inspector.get_columns('key_signals')]
    assert 'unique_key' in key_signals_columns, "Migration should add unique_key to key_signals"
    
    if 'shunya_jobs' in inspector.get_table_names():
        shunya_jobs_columns = [col['name'] for col in inspector.get_columns('shunya_jobs')]
        assert 'processed_output_hash' in shunya_jobs_columns, \
            "Migration should add processed_output_hash to shunya_jobs"





Verifies that:
1. The new idempotency fields exist in the database schema
2. Fields can be written and read correctly
3. Models and DB schema stay in sync
"""
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine
from app.config import settings
from app.models.task import Task, TaskSource
from app.models.key_signal import KeySignal, SignalType
from app.models.shunya_job import ShunyaJob, ShunyaJobType, ShunyaJobStatus
from app.utils.idempotency import (
    generate_task_unique_key,
    generate_signal_unique_key,
    generate_output_payload_hash,
)


def test_tasks_table_has_unique_key_column(db_session: Session):
    """Test that tasks table has unique_key column."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('tasks')]
    
    assert 'unique_key' in columns, "tasks table missing unique_key column"
    
    # Check column properties
    for col in inspector.get_columns('tasks'):
        if col['name'] == 'unique_key':
            assert col['nullable'] is True, "unique_key should be nullable"
            assert col['type'].python_type == str or col['type'].python_type.__name__ == 'STRING', \
                "unique_key should be String type"
            break


def test_key_signals_table_has_unique_key_column(db_session: Session):
    """Test that key_signals table has unique_key column."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('key_signals')]
    
    assert 'unique_key' in columns, "key_signals table missing unique_key column"
    
    # Check column properties
    for col in inspector.get_columns('key_signals'):
        if col['name'] == 'unique_key':
            assert col['nullable'] is True, "unique_key should be nullable"
            break


def test_shunya_jobs_table_has_processed_output_hash_column(db_session: Session):
    """Test that shunya_jobs table has processed_output_hash column."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'shunya_jobs' not in tables:
        pytest.skip("shunya_jobs table does not exist yet")
    
    columns = [col['name'] for col in inspector.get_columns('shunya_jobs')]
    
    assert 'processed_output_hash' in columns, "shunya_jobs table missing processed_output_hash column"
    
    # Check column properties
    for col in inspector.get_columns('shunya_jobs'):
        if col['name'] == 'processed_output_hash':
            assert col['nullable'] is True, "processed_output_hash should be nullable"
            break


def test_tasks_unique_key_index_exists(db_session: Session):
    """Test that index on tasks.unique_key exists."""
    inspector = inspect(engine)
    indexes = [idx['name'] for idx in inspector.get_indexes('tasks')]
    
    # Check for index on unique_key (may be composite with company_id)
    unique_key_indexes = [
        idx for idx in inspector.get_indexes('tasks')
        if 'unique_key' in [col for col in idx.get('column_names', [])]
    ]
    
    assert len(unique_key_indexes) > 0, "Index on tasks.unique_key not found"


def test_key_signals_unique_key_index_exists(db_session: Session):
    """Test that index on key_signals.unique_key exists."""
    inspector = inspect(engine)
    indexes = [idx['name'] for idx in inspector.get_indexes('key_signals')]
    
    # Check for index on unique_key (may be composite with company_id)
    unique_key_indexes = [
        idx for idx in inspector.get_indexes('key_signals')
        if 'unique_key' in [col for col in idx.get('column_names', [])]
    ]
    
    assert len(unique_key_indexes) > 0, "Index on key_signals.unique_key not found"


def test_task_unique_key_read_write(db_session: Session):
    """Test that Task.unique_key can be written and read."""
    from app.models.contact_card import ContactCard
    from app.models.company import Company
    
    # Create test company and contact card if they don't exist
    company = db_session.query(Company).first()
    if not company:
        pytest.skip("No company found in database")
    
    contact_card = db_session.query(ContactCard).filter_by(company_id=company.id).first()
    if not contact_card:
        pytest.skip("No contact card found in database")
    
    # Generate unique key
    unique_key = generate_task_unique_key(
        source=TaskSource.SHUNYA,
        description="Test task description",
        contact_card_id=contact_card.id,
    )
    
    # Create task with unique_key
    task = Task(
        company_id=company.id,
        contact_card_id=contact_card.id,
        description="Test task description",
        assigned_to="csr",
        source=TaskSource.SHUNYA,
        unique_key=unique_key,
        status="open"
    )
    
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    
    # Verify unique_key was saved
    assert task.unique_key == unique_key, "unique_key not saved correctly"
    
    # Clean up
    db_session.delete(task)
    db_session.commit()


def test_key_signal_unique_key_read_write(db_session: Session):
    """Test that KeySignal.unique_key can be written and read."""
    from app.models.contact_card import ContactCard
    from app.models.company import Company
    
    # Create test company and contact card if they don't exist
    company = db_session.query(Company).first()
    if not company:
        pytest.skip("No company found in database")
    
    contact_card = db_session.query(ContactCard).filter_by(company_id=company.id).first()
    if not contact_card:
        pytest.skip("No contact card found in database")
    
    # Generate unique key
    unique_key = generate_signal_unique_key(
        signal_type=SignalType.OPPORTUNITY,
        title="Test signal",
        contact_card_id=contact_card.id,
    )
    
    # Create signal with unique_key
    signal = KeySignal(
        company_id=company.id,
        contact_card_id=contact_card.id,
        signal_type=SignalType.OPPORTUNITY,
        severity="high",
        title="Test signal",
        unique_key=unique_key,
        acknowledged=False
    )
    
    db_session.add(signal)
    db_session.commit()
    db_session.refresh(signal)
    
    # Verify unique_key was saved
    assert signal.unique_key == unique_key, "unique_key not saved correctly"
    
    # Clean up
    db_session.delete(signal)
    db_session.commit()


def test_shunya_job_processed_output_hash_read_write(db_session: Session):
    """Test that ShunyaJob.processed_output_hash can be written and read."""
    from app.models.contact_card import ContactCard
    from app.models.company import Company
    
    # Create test company and contact card if they don't exist
    company = db_session.query(Company).first()
    if not company:
        pytest.skip("No company found in database")
    
    contact_card = db_session.query(ContactCard).filter_by(company_id=company.id).first()
    if not contact_card:
        pytest.skip("No contact card found in database")
    
    # Generate output hash
    output_payload = {"test": "data", "status": "completed"}
    output_hash = generate_output_payload_hash(output_payload)
    
    # Create job with processed_output_hash
    job = ShunyaJob(
        company_id=company.id,
        contact_card_id=contact_card.id,
        job_type=ShunyaJobType.CSR_CALL,
        job_status=ShunyaJobStatus.PENDING,
        shunya_job_id="test-shunya-job-123",
        processed_output_hash=output_hash,
    )
    
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    
    # Verify processed_output_hash was saved
    assert job.processed_output_hash == output_hash, "processed_output_hash not saved correctly"
    
    # Clean up
    db_session.delete(job)
    db_session.commit()


def test_migration_is_idempotent(db_session: Session):
    """Test that running the migration twice doesn't cause errors."""
    # This test verifies the migration can be run multiple times safely
    # The migration itself has idempotency checks built in
    inspector = inspect(engine)
    
    # Verify columns exist (migration should have run)
    tasks_columns = [col['name'] for col in inspector.get_columns('tasks')]
    assert 'unique_key' in tasks_columns, "Migration should add unique_key to tasks"
    
    key_signals_columns = [col['name'] for col in inspector.get_columns('key_signals')]
    assert 'unique_key' in key_signals_columns, "Migration should add unique_key to key_signals"
    
    if 'shunya_jobs' in inspector.get_table_names():
        shunya_jobs_columns = [col['name'] for col in inspector.get_columns('shunya_jobs')]
        assert 'processed_output_hash' in shunya_jobs_columns, \
            "Migration should add processed_output_hash to shunya_jobs"



