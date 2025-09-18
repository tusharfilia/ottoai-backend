from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.schema import CreateTable
from fastapi import Request, Depends
from typing import Generator
import os

# Import centralized configuration
from app.config import settings

DATABASE_URL = settings.DATABASE_URL
DEBUG_SQL = os.getenv("DEBUG_SQL", "false").lower() == "true"

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=DEBUG_SQL)
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
    """Get database session with tenant context."""
    # Get tenant_id from request state (set by middleware)
    tenant_id = getattr(request.state, 'tenant_id', None)
    
    if not tenant_id:
        # For endpoints that don't require tenant context (like health checks)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        # Create tenant-scoped session
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
    column_name = column.compile(dialect=engine.dialect)
    column_type = column.type.compile(engine.dialect)
    engine.execute(f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}')

# Create tables
def init_db():
    # Import all models here so that Base knows about them
    from .models import call, sales_rep, sales_manager, service, scheduled_call, company
    
    inspector = inspect(engine)
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # For each table, check and add missing columns
    for table_name, model in [
        ("calls", call.Call),
        ("sales_reps", sales_rep.SalesRep),
        ("sales_managers", sales_manager.SalesManager),
        ("services", service.Service),
        ("scheduled_calls", scheduled_call.ScheduledCall),
        ("companies", company.Company)  # Add companies table
    ]:
        existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
        model_columns = model.__table__.columns
        
        for column in model_columns:
            if column.name not in existing_columns:
                try:
                    add_column(engine, table_name, column)
                    print(f"Added column {column.name} to table {table_name}")
                except Exception as e:
                    print(f"Error adding column {column.name} to {table_name}: {str(e)}") 