"""
RAG Document model for tracking documents indexed in UWC's knowledge base.
Tracks SOPs, sales scripts, objection handlers, and training materials.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, Enum, Boolean
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
import enum


class DocumentType(str, enum.Enum):
    """Document categories for RAG indexing."""
    SOP = "sop"  # Standard Operating Procedure
    SCRIPT = "script"  # Sales script
    OBJECTION_HANDLER = "objection_handler"  # How to handle objections
    PRODUCT_INFO = "product_info"  # Product specifications
    TRAINING_MATERIAL = "training_material"  # Training videos, presentations
    POLICY = "policy"  # Company policies
    FAQ = "faq"  # Frequently asked questions


class IndexingStatus(str, enum.Enum):
    """Document indexing pipeline status."""
    PENDING = "pending"  # Uploaded, not yet sent to UWC
    PROCESSING = "processing"  # UWC is indexing
    INDEXED = "indexed"  # Successfully indexed
    FAILED = "failed"  # Indexing failed
    DELETED = "deleted"  # Document deleted from index


class RAGDocument(Base):
    """
    Tracks documents indexed in UWC RAG system.
    
    Features:
    - Tenant isolation for multi-tenancy
    - Document type categorization
    - Indexing status tracking
    - UWC job correlation
    - Soft deletion support
    """
    __tablename__ = "rag_documents"
    
    # Primary key
    id = Column(String, primary_key=True)  # UUID
    
    # Foreign keys (with indexes)
    tenant_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Document Metadata
    filename = Column(String, nullable=False)
    file_url = Column(String, nullable=False)  # S3 URL
    file_size_bytes = Column(Integer, nullable=True)
    content_type = Column(String, nullable=True)  # MIME type (application/pdf, etc.)
    document_type = Column(Enum(DocumentType), nullable=False, index=True)
    
    # Indexing Status
    indexing_status = Column(Enum(IndexingStatus), default=IndexingStatus.PENDING, nullable=False, index=True)
    uwc_job_id = Column(String, index=True, nullable=True)  # Set when sent to UWC
    indexed_at = Column(DateTime, nullable=True)  # When indexing completed
    chunk_count = Column(Integer, default=0)  # How many chunks/vectors created
    
    # Error Handling
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)  # How many times we retried indexing
    
    # Soft Deletion
    deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", foreign_keys=[tenant_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
    
    # Multi-tenant performance indexes
    __table_args__ = (
        Index('ix_rag_docs_tenant', 'tenant_id'),  # List all docs for tenant
        Index('ix_rag_docs_tenant_type', 'tenant_id', 'document_type'),  # Filter by type
        Index('ix_rag_docs_tenant_status', 'tenant_id', 'indexing_status'),  # Filter by status
        Index('ix_rag_docs_uwc_job', 'uwc_job_id'),  # Lookup by UWC job
        Index('ix_rag_docs_tenant_deleted', 'tenant_id', 'deleted'),  # Filter out deleted
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "filename": self.filename,
            "file_url": self.file_url,
            "file_size_bytes": self.file_size_bytes,
            "content_type": self.content_type,
            "document_type": self.document_type.value if self.document_type else None,
            "indexing_status": self.indexing_status.value if self.indexing_status else None,
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "uploaded_by": self.uploaded_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deleted": self.deleted
        }


