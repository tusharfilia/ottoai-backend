"""
Idempotency record model for tracking duplicate requests.
"""
from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class IdempotencyRecord(Base):
    """Model for storing idempotency records."""
    
    __tablename__ = "idempotency_records"
    
    id = Column(Integer, primary_key=True, index=True)
    composite_key = Column(String(255), unique=True, index=True, nullable=False)
    tenant_id = Column(String(255), nullable=False, index=True)
    idempotency_key = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_composite_key', 'composite_key'),
    )
    
    def __repr__(self):
        return f"<IdempotencyRecord(id={self.id}, key={self.idempotency_key}, tenant={self.tenant_id})>"
