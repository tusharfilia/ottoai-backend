"""
RAG Query model for logging Ask Otto queries and responses.
Enables analytics, quality tracking, and user feedback collection.
"""
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime


class RAGQuery(Base):
    """
    Logs Ask Otto queries and responses for analytics and improvement.
    
    Features:
    - Query/answer logging
    - Citation tracking (which documents were used)
    - Confidence scoring
    - Performance tracking (latency)
    - User feedback collection
    - Role-based scoping for analytics
    """
    __tablename__ = "rag_queries"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    tenant_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    
    # Query Details
    query_text = Column(Text, nullable=False)  # The question user asked
    answer_text = Column(Text, nullable=False)  # Otto's response
    
    # Citations (which documents/calls were used)
    citations = Column(JSON, nullable=True)
    # Format: [
    #   {
    #     "doc_id": "doc_123",
    #     "filename": "sales_script.pdf",
    #     "chunk_text": "Always set agenda early...",
    #     "similarity_score": 0.92,
    #     "call_id": null
    #   }
    # ]
    
    # Quality Metrics
    confidence_score = Column(Float, nullable=True)  # 0-1, how confident Otto is
    result_count = Column(Integer, default=0)  # How many results returned
    
    # Performance Tracking
    latency_ms = Column(Integer, nullable=True)  # How long query took
    uwc_request_id = Column(String, nullable=True)  # UWC correlation ID
    
    # User Feedback (for quality improvement)
    user_rating = Column(Integer, nullable=True)  # 1-5 stars (optional)
    user_feedback = Column(Text, nullable=True)  # Free-form feedback
    feedback_received_at = Column(DateTime, nullable=True)
    
    # Context (for analytics)
    user_role = Column(String, nullable=True)  # Which role asked (exec, manager, csr, rep)
    query_context = Column(JSON, nullable=True)  # Additional context (call_id, etc.)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    company = relationship("Company", foreign_keys=[tenant_id])
    user = relationship("User", foreign_keys=[user_id])
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_rag_queries_tenant_user', 'tenant_id', 'user_id'),  # User's query history
        Index('ix_rag_queries_tenant_created', 'tenant_id', 'created_at'),  # Recent queries
        Index('ix_rag_queries_user_created', 'user_id', 'created_at'),  # User timeline
        Index('ix_rag_queries_tenant_role', 'tenant_id', 'user_role'),  # Analytics by role
        Index('ix_rag_queries_tenant_rating', 'tenant_id', 'user_rating'),  # Quality tracking
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "query_text": self.query_text,
            "answer_text": self.answer_text,
            "citations": self.citations,
            "confidence_score": self.confidence_score,
            "result_count": self.result_count,
            "latency_ms": self.latency_ms,
            "user_rating": self.user_rating,
            "user_role": self.user_role,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }



