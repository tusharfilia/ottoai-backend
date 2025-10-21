"""
RAG telemetry model for tracking Ask Otto query metrics.
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Index
from sqlalchemy.sql import func
from app.database import Base


class RAGTelemetry(Base):
    """Model for storing RAG query telemetry data."""
    
    __tablename__ = "rag_telemetry"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    user_role = Column(String(50), nullable=False, index=True)
    
    # Query data
    query_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    
    # Citation metrics
    citations_count = Column(Integer, nullable=False, default=0)
    avg_citation_score = Column(Float, nullable=False, default=0.0)
    
    # Performance metrics
    latency_ms = Column(Float, nullable=False)
    tokens_in = Column(Integer, nullable=False, default=0)
    tokens_out = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    
    # Quality metrics
    groundedness_score = Column(Float, nullable=False, default=0.0)
    degraded_mode = Column(Boolean, nullable=False, default=False)
    fallback_used = Column(Boolean, nullable=False, default=False)
    
    # External tracking
    uwc_request_id = Column(String(255), nullable=True, index=True)
    
    # Quality indicators
    has_citations = Column(Boolean, nullable=False, default=False)
    is_grounded = Column(Boolean, nullable=False, default=False)
    is_high_quality = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_user_role', 'user_role', 'created_at'),
        Index('idx_quality_metrics', 'is_high_quality', 'groundedness_score'),
        Index('idx_cost_tracking', 'tenant_id', 'cost_usd', 'created_at'),
    )
    
    def __repr__(self):
        return f"<RAGTelemetry(id={self.id}, tenant={self.tenant_id}, user={self.user_id}, latency={self.latency_ms}ms)>"
