from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import ProgrammingError, OperationalError, NoSuchTableError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.schema import CreateTable
from fastapi import Request, Depends, HTTPException
from typing import Generator
import os

# Import centralized configuration
from app.config import settings

DATABASE_URL = settings.DATABASE_URL
DEBUG_SQL = os.getenv("DEBUG_SQL", "false").lower() == "true"

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Production-ready connection pool configuration
engine = create_engine(
    DATABASE_URL,
    echo=DEBUG_SQL,
    pool_size=20,  # Normal connections (adjust based on load)
    max_overflow=40,  # Burst capacity (total = 60 connections max)
    pool_timeout=30,  # Wait 30s for connection before failing
    pool_recycle=1800,  # Recycle connections every 30 minutes
    pool_pre_ping=True,  # Verify connections before use (prevents stale connections)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class TenantScopedSession(Session):
    """Database session that automatically scopes queries by tenant_id."""
    
    def __init__(self, tenant_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant_id = tenant_id
    
    def query(self, *entities, **kwargs):
        """Override query to automatically add tenant filtering."""
        query = super().query(*entities, **kwargs)
        
        # Add tenant filtering for models that have company_id
        for entity in entities:
            if hasattr(entity, 'company_id'):
                query = query.filter(entity.company_id == self.tenant_id)
        
        return query


# Dependency for getting database session with tenant context
def get_db(request: Request) -> Generator[Session, None, None]:
    """
    Get database session with mandatory tenant context.
    
    This dependency enforces tenant isolation by requiring tenant_id
    for all database operations. Only health check endpoints are exempt.
    """
    # Get tenant_id from request state (set by middleware)
    tenant_id = getattr(request.state, 'tenant_id', None)
    
    # Only allow non-tenant sessions for specific exempt endpoints
    exempt_paths = [
        "/health", "/metrics", "/docs", "/redoc", "/openapi.json",
        "/call-complete", "/callrail/", "/pre-call", "/call-modified",
        "/sms/callrail-webhook", "/sms/twilio-webhook", "/twilio-webhook",
        "/mobile/twilio-", "/clerk-webhook"
    ]
    is_exempt = any(request.url.path.startswith(path) for path in exempt_paths)
    
    if not tenant_id and not is_exempt:
        # For all protected endpoints, tenant_id is mandatory
        from app.obs.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Missing tenant_id for protected endpoint: {request.url.path}")
        raise HTTPException(
            status_code=403,
            detail="Tenant context required for this endpoint"
        )
    
    if not tenant_id:
        # Only for exempt endpoints (health checks, docs)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        # Create tenant-scoped session for all protected endpoints
        db = TenantScopedSession(tenant_id, bind=engine)
        try:
            yield db
        finally:
            db.close()


# Legacy dependency for backward compatibility (use with caution)
def get_db_legacy() -> Generator[Session, None, None]:
    """Legacy database dependency without tenant scoping."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_column(engine, table_name, column):
    """Add a column to a table using SQLAlchemy 2.0 API."""
    # Use column.name directly (not compiled) to avoid table-qualified names
    column_name = column.name
    column_type = column.type.compile(engine.dialect)
    
    # SQLite doesn't support IF NOT EXISTS in ALTER TABLE ADD COLUMN
    # Check if column exists first for SQLite
    dialect = engine.dialect.name
    if dialect == 'sqlite':
        inspector = inspect(engine)
        try:
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
            if column_name in existing_columns:
                return  # Column already exists, skip
        except NoSuchTableError:
            pass  # Table doesn't exist, will be created by migrations
        sql = text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}')
    else:
        # PostgreSQL supports IF NOT EXISTS
        sql = text(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}')
    
    with engine.begin() as conn:
        try:
            conn.execute(sql)
        except (ProgrammingError, OperationalError) as e:
            # Ignore if column already exists
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            if "already exists" not in error_msg.lower() and "duplicate" not in error_msg.lower():
                raise

# Create tables
def init_db():
    # Import all models here so that Base knows about them
    from .models import (
        call, 
        sales_rep, 
        sales_manager, 
        service, 
        scheduled_call, 
        company,
        user,
        transcript_analysis,
        call_transcript,
        call_analysis,
        rag_document,
        rag_query,
        followup_draft,
        personal_clone_job,
        audit_log,
        contact_card,
        lead,
        appointment,
        rep_shift,
        recording_session,
        recording_transcript,
        recording_analysis,
        task,
        key_signal,
        lead_status_history,
        rep_assignment_history,
        event_log,
        sop_compliance_result
    )
    
    inspector = inspect(engine)
    
    # Create tables if they don't exist
    # Catch duplicate index/table errors (common when migrations have already run)
    # SQLite raises OperationalError, PostgreSQL raises ProgrammingError
    try:
        Base.metadata.create_all(bind=engine)
    except (ProgrammingError, OperationalError) as e:
        # Ignore duplicate index/table errors - these are expected when migrations have run
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "already exists" not in error_msg.lower() and "duplicate" not in error_msg.lower():
            # Re-raise if it's not a duplicate error
            raise
        # Log but don't fail on duplicate index/table errors
        print(f"Note: Some indexes/tables already exist (expected if migrations ran): {error_msg[:100]}")
    
    # For each table, check and add missing columns
    for table_name, model in [
        ("calls", call.Call),
        ("sales_reps", sales_rep.SalesRep),
        ("sales_managers", sales_manager.SalesManager),
        ("services", service.Service),
        ("scheduled_calls", scheduled_call.ScheduledCall),
        ("companies", company.Company),
        ("users", user.User),
        ("transcript_analyses", transcript_analysis.TranscriptAnalysis),
        ("call_transcripts", call_transcript.CallTranscript),
        ("call_analysis", call_analysis.CallAnalysis),
        ("rag_documents", rag_document.RAGDocument),
        ("rag_queries", rag_query.RAGQuery),
        ("followup_drafts", followup_draft.FollowUpDraft),
        ("personal_clone_jobs", personal_clone_job.PersonalCloneJob),
        ("audit_logs", audit_log.AuditLog),
        ("contact_cards", contact_card.ContactCard),
        ("leads", lead.Lead),
        ("appointments", appointment.Appointment),
        ("rep_shifts", rep_shift.RepShift),
        ("recording_sessions", recording_session.RecordingSession),
        ("recording_transcripts", recording_transcript.RecordingTranscript),
        ("recording_analyses", recording_analysis.RecordingAnalysis),
        ("tasks", task.Task),
        ("key_signals", key_signal.KeySignal),
        ("lead_status_history", lead_status_history.LeadStatusHistory),
        ("rep_assignment_history", rep_assignment_history.RepAssignmentHistory),
        ("event_logs", event_log.EventLog),
        ("sop_compliance_results", sop_compliance_result.SopComplianceResult)
    ]:
        # Check if table exists before trying to get columns
        try:
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
        except NoSuchTableError:
            # Table doesn't exist yet, skip column checks (will be created by migrations or create_all)
            print(f"Table {table_name} does not exist yet, skipping column checks")
            continue
        
        model_columns = model.__table__.columns
        
        for column in model_columns:
            if column.name not in existing_columns:
                try:
                    add_column(engine, table_name, column)
                    print(f"Added column {column.name} to table {table_name}")
                except Exception as e:
                    print(f"Error adding column {column.name} to {table_name}: {str(e)}") 
        rep_shift,
        recording_session,
        recording_transcript,
        recording_analysis,
        task,
        key_signal,
        lead_status_history,
        rep_assignment_history,
        event_log,
        sop_compliance_result
    )
    
    inspector = inspect(engine)
    
    # Create tables if they don't exist
    # Catch duplicate index/table errors (common when migrations have already run)
    # SQLite raises OperationalError, PostgreSQL raises ProgrammingError
    try:
        Base.metadata.create_all(bind=engine)
    except (ProgrammingError, OperationalError) as e:
        # Ignore duplicate index/table errors - these are expected when migrations have run
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "already exists" not in error_msg.lower() and "duplicate" not in error_msg.lower():
            # Re-raise if it's not a duplicate error
            raise
        # Log but don't fail on duplicate index/table errors
        print(f"Note: Some indexes/tables already exist (expected if migrations ran): {error_msg[:100]}")
    
    # For each table, check and add missing columns
    for table_name, model in [
        ("calls", call.Call),
        ("sales_reps", sales_rep.SalesRep),
        ("sales_managers", sales_manager.SalesManager),
        ("services", service.Service),
        ("scheduled_calls", scheduled_call.ScheduledCall),
        ("companies", company.Company),
        ("users", user.User),
        ("transcript_analyses", transcript_analysis.TranscriptAnalysis),
        ("call_transcripts", call_transcript.CallTranscript),
        ("call_analysis", call_analysis.CallAnalysis),
        ("rag_documents", rag_document.RAGDocument),
        ("rag_queries", rag_query.RAGQuery),
        ("followup_drafts", followup_draft.FollowUpDraft),
        ("personal_clone_jobs", personal_clone_job.PersonalCloneJob),
        ("audit_logs", audit_log.AuditLog),
        ("contact_cards", contact_card.ContactCard),
        ("leads", lead.Lead),
        ("appointments", appointment.Appointment),
        ("rep_shifts", rep_shift.RepShift),
        ("recording_sessions", recording_session.RecordingSession),
        ("recording_transcripts", recording_transcript.RecordingTranscript),
        ("recording_analyses", recording_analysis.RecordingAnalysis),
        ("tasks", task.Task),
        ("key_signals", key_signal.KeySignal),
        ("lead_status_history", lead_status_history.LeadStatusHistory),
        ("rep_assignment_history", rep_assignment_history.RepAssignmentHistory),
        ("event_logs", event_log.EventLog),
        ("sop_compliance_results", sop_compliance_result.SopComplianceResult)
    ]:
        # Check if table exists before trying to get columns
        try:
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
        except NoSuchTableError:
            # Table doesn't exist yet, skip column checks (will be created by migrations or create_all)
            print(f"Table {table_name} does not exist yet, skipping column checks")
            continue
        
        model_columns = model.__table__.columns
        
        for column in model_columns:
            if column.name not in existing_columns:
                try:
                    add_column(engine, table_name, column)
                    print(f"Added column {column.name} to table {table_name}")
                except Exception as e:
                    print(f"Error adding column {column.name} to {table_name}: {str(e)}") 
        rep_shift,
        recording_session,
        recording_transcript,
        recording_analysis,
        task,
        key_signal,
        lead_status_history,
        rep_assignment_history,
        event_log,
        sop_compliance_result
    )
    
    inspector = inspect(engine)
    
    # Create tables if they don't exist
    # Catch duplicate index/table errors (common when migrations have already run)
    # SQLite raises OperationalError, PostgreSQL raises ProgrammingError
    try:
        Base.metadata.create_all(bind=engine)
    except (ProgrammingError, OperationalError) as e:
        # Ignore duplicate index/table errors - these are expected when migrations have run
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "already exists" not in error_msg.lower() and "duplicate" not in error_msg.lower():
            # Re-raise if it's not a duplicate error
            raise
        # Log but don't fail on duplicate index/table errors
        print(f"Note: Some indexes/tables already exist (expected if migrations ran): {error_msg[:100]}")
    
    # For each table, check and add missing columns
    for table_name, model in [
        ("calls", call.Call),
        ("sales_reps", sales_rep.SalesRep),
        ("sales_managers", sales_manager.SalesManager),
        ("services", service.Service),
        ("scheduled_calls", scheduled_call.ScheduledCall),
        ("companies", company.Company),
        ("users", user.User),
        ("transcript_analyses", transcript_analysis.TranscriptAnalysis),
        ("call_transcripts", call_transcript.CallTranscript),
        ("call_analysis", call_analysis.CallAnalysis),
        ("rag_documents", rag_document.RAGDocument),
        ("rag_queries", rag_query.RAGQuery),
        ("followup_drafts", followup_draft.FollowUpDraft),
        ("personal_clone_jobs", personal_clone_job.PersonalCloneJob),
        ("audit_logs", audit_log.AuditLog),
        ("contact_cards", contact_card.ContactCard),
        ("leads", lead.Lead),
        ("appointments", appointment.Appointment),
        ("rep_shifts", rep_shift.RepShift),
        ("recording_sessions", recording_session.RecordingSession),
        ("recording_transcripts", recording_transcript.RecordingTranscript),
        ("recording_analyses", recording_analysis.RecordingAnalysis),
        ("tasks", task.Task),
        ("key_signals", key_signal.KeySignal),
        ("lead_status_history", lead_status_history.LeadStatusHistory),
        ("rep_assignment_history", rep_assignment_history.RepAssignmentHistory),
        ("event_logs", event_log.EventLog),
        ("sop_compliance_results", sop_compliance_result.SopComplianceResult)
    ]:
        # Check if table exists before trying to get columns
        try:
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
        except NoSuchTableError:
            # Table doesn't exist yet, skip column checks (will be created by migrations or create_all)
            print(f"Table {table_name} does not exist yet, skipping column checks")
            continue
        
        model_columns = model.__table__.columns
        
        for column in model_columns:
            if column.name not in existing_columns:
                try:
                    add_column(engine, table_name, column)
                    print(f"Added column {column.name} to table {table_name}")
                except Exception as e:
                    print(f"Error adding column {column.name} to {table_name}: {str(e)}") 