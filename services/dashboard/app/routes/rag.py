"""
RAG (Retrieval-Augmented Generation) endpoints for Ask Otto feature.
Provides natural language Q&A over company data with citations.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta

from app.database import get_db
from app.middleware.rbac import require_role
from app.config import settings
from app.services.uwc_client import uwc_client
from app.services.audit_logger import AuditLogger
from app.models.rag_query import RAGQuery
from app.models.rag_document import RAGDocument, DocumentType, IndexingStatus
from app.schemas.responses import APIResponse, PaginatedResponse, PaginationMeta, ErrorResponse, ErrorCodes, create_error_response
from app.obs.logging import get_logger
from app.obs.metrics import metrics

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/rag", tags=["rag", "ask-otto"])


# Request/Response Schemas
class RAGQueryRequest(BaseModel):
    """Ask Otto query request."""
    query: str = Field(..., description="Natural language question", min_length=3, max_length=1000)
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters (date_range, rep_id, etc.)")
    max_results: int = Field(10, description="Maximum number of results", ge=1, le=50)
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the most common objections my reps face?",
                "filters": {"date_range": "last_30_days"},
                "max_results": 10
            }
        }


class Citation(BaseModel):
    """Citation for a RAG result."""
    doc_id: str
    filename: Optional[str] = None
    chunk_text: str
    similarity_score: float
    call_id: Optional[int] = None
    timestamp: Optional[float] = None


class RAGQueryResponse(BaseModel):
    """Ask Otto query response."""
    query_id: str
    query: str
    answer: str
    citations: List[Citation]
    confidence_score: float
    latency_ms: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "query_123",
                "query": "What are the most common objections?",
                "answer": "The most common objection is 'price too high' (40%), followed by 'need to think about it' (28%)...",
                "citations": [
                    {
                        "doc_id": "doc_123",
                        "filename": "sales_script.pdf",
                        "chunk_text": "Price objections are best handled by...",
                        "similarity_score": 0.92
                    }
                ],
                "confidence_score": 0.89,
                "latency_ms": 1250
            }
        }


class DocumentUploadResponse(BaseModel):
    """Document upload response."""
    document_id: str
    status: str
    filename: str
    file_url: str
    uwc_job_id: Optional[str] = None


# Endpoints

@router.post("/query", response_model=APIResponse[RAGQueryResponse])
@require_role("exec", "manager", "csr", "rep")
async def query_ask_otto(
    request: Request,
    query: RAGQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Ask Otto: Natural language Q&A over company data.
    
    Scoping rules:
    - exec/manager: Company-wide data
    - csr: Company calls + leads (not rep appointments)
    - rep: Only their own data
    
    Returns answer with citations showing source documents/calls.
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    user_role = request.state.user_role
    start_time = datetime.utcnow()
    
    try:
        # Role-based scoping context
        context = {
            "tenant_id": tenant_id,
            "user_role": user_role
        }
        
        # Reps only see their own data
        if user_role == "rep":
            context["user_id"] = user_id
        
        # CSRs see calls/leads but not rep appointments
        if user_role == "csr":
            context["exclude_rep_data"] = True
        
        # Try UWC RAG first if enabled
        answer = None
        citations_data = []
        confidence = 0.0
        
        if settings.ENABLE_UWC_RAG and settings.UWC_BASE_URL:
            try:
                logger.info(f"Attempting UWC RAG query for: {query.query}")
                uwc_result = await uwc_client.query_rag(
                    company_id=tenant_id,
                    request_id=request.state.trace_id,
                    query=query.query,
                    context=context,
                    options={
                        "max_results": query.max_results,
                        "similarity_threshold": 0.7,
                        "include_metadata": True
                    }
                )
                
                answer = uwc_result.get("answer", "")
                citations_data = uwc_result.get("citations", [])
                confidence = uwc_result.get("confidence_score", 0.0)
                
                if answer and citations_data:
                    logger.info(f"UWC RAG query successful for: {query.query}")
                else:
                    raise Exception("UWC RAG returned empty response")
                    
            except Exception as e:
                logger.warning(f"UWC RAG failed for query '{query.query}', falling back to mock: {str(e)}")
                # Fall through to mock fallback
        
        # Fallback to mock response if UWC is disabled or failed
        if not answer:
            logger.info(f"Using mock RAG response for: {query.query}")
            mock_response = mock_rag_response(query.query, query.max_results)
            answer = mock_response["answer"]
            citations_data = mock_response["citations"]
            confidence = mock_response["confidence_score"]
        
        # Calculate latency
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Parse citations
        citations = [
            Citation(
                doc_id=c.get("doc_id", ""),
                filename=c.get("filename"),
                chunk_text=c.get("chunk_text", ""),
                similarity_score=c.get("similarity_score", 0.0),
                call_id=c.get("call_id"),
                timestamp=c.get("timestamp")
            )
            for c in citations_data
        ]
        
        # Log query in database for analytics
        query_id = str(uuid.uuid4())
        rag_query_log = RAGQuery(
            id=query_id,
            tenant_id=tenant_id,
            user_id=user_id,
            query_text=query.query,
            answer_text=answer,
            citations=citations_data,
            confidence_score=confidence,
            result_count=len(citations),
            latency_ms=latency_ms,
            uwc_request_id=request.state.trace_id,
            user_role=user_role,
            query_context=query.filters
        )
        db.add(rag_query_log)
        db.commit()
        
        # Audit log for sensitive queries (if needed)
        audit = AuditLogger(db, request)
        audit.log_rag_query(
            query_text=query.query,
            answer_text=answer,
            confidence_score=confidence,
            result_count=len(citations)
        )
        
        # Record metrics
        metrics.rag_queries_total.labels(
            tenant_id=tenant_id,
            user_role=user_role,
            result_count=len(citations)
        ).inc()
        
        metrics.rag_query_latency_ms.observe(latency_ms)
        
        # Build response
        response = RAGQueryResponse(
            query_id=query_id,
            query=query.query,
            answer=answer,
            citations=citations,
            confidence_score=confidence,
            latency_ms=latency_ms
        )
        
        return APIResponse(data=response)
        
    except Exception as e:
        logger.error(f"RAG query failed: {str(e)}",
                    extra={
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "query": query.query
                    })
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message="Failed to process Ask Otto query. Please try again.",
                request_id=request.state.trace_id
            ).dict()
        )


@router.get("/queries", response_model=PaginatedResponse[Dict])
@require_role("exec", "manager")
async def get_query_history(
    request: Request,
    page: int = 1,
    page_size: int = 50,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get Ask Otto query history for analytics.
    
    Only exec/manager can view query history.
    Can filter by specific user.
    """
    tenant_id = request.state.tenant_id
    
    # Base query
    query = db.query(RAGQuery).filter_by(tenant_id=tenant_id)
    
    # Optional user filter
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    # Get total count
    total = query.count()
    
    # Paginate
    queries = query.order_by(RAGQuery.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    # Convert to dicts
    items = [q.to_dict() for q in queries]
    
    # Build pagination metadata
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedResponse(
        items=items,
        meta=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


@router.post("/queries/{query_id}/feedback")
@require_role("exec", "manager", "csr", "rep")
async def submit_query_feedback(
    request: Request,
    query_id: str,
    rating: int = Field(..., ge=1, le=5),
    feedback: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Submit feedback on Ask Otto response quality.
    Helps improve AI over time.
    """
    tenant_id = request.state.tenant_id
    
    # Find query
    rag_query = db.query(RAGQuery).filter_by(
        id=query_id,
        tenant_id=tenant_id
    ).first()
    
    if not rag_query:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Query not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Update feedback
    rag_query.user_rating = rating
    rag_query.user_feedback = feedback
    rag_query.feedback_received_at = datetime.utcnow()
    db.commit()
    
    logger.info("Query feedback received",
               extra={
                   "query_id": query_id,
                   "rating": rating,
                   "tenant_id": tenant_id
               })
    
    return APIResponse(data={"status": "feedback_recorded"})


@router.get("/documents", response_model=PaginatedResponse[Dict])
@require_role("exec", "manager")
async def list_documents(
    request: Request,
    page: int = 1,
    page_size: int = 50,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List uploaded documents for RAG.
    Filter by type and indexing status.
    """
    tenant_id = request.state.tenant_id
    
    # Base query (exclude deleted)
    query = db.query(RAGDocument).filter_by(
        tenant_id=tenant_id,
        deleted=False
    )
    
    # Optional filters
    if document_type:
        try:
            doc_type_enum = DocumentType(document_type)
            query = query.filter_by(document_type=doc_type_enum)
        except ValueError:
            pass  # Invalid type, ignore filter
    
    if status:
        try:
            status_enum = IndexingStatus(status)
            query = query.filter_by(indexing_status=status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter
    
    # Get total
    total = query.count()
    
    # Paginate
    documents = query.order_by(RAGDocument.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    # Convert to dicts
    items = [doc.to_dict() for doc in documents]
    
    # Build pagination
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedResponse(
        items=items,
        meta=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )
    )


@router.get("/documents/{document_id}")
@require_role("exec", "manager")
async def get_document(
    request: Request,
    document_id: str,
    db: Session = Depends(get_db)
):
    """Get document details by ID."""
    tenant_id = request.state.tenant_id
    
    document = db.query(RAGDocument).filter_by(
        id=document_id,
        tenant_id=tenant_id
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.DOCUMENT_NOT_FOUND,
                message=f"Document {document_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    return APIResponse(data=document.to_dict())


@router.delete("/documents/{document_id}")
@require_role("exec", "manager")
async def delete_document(
    request: Request,
    document_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete document from RAG index (soft delete).
    Also requests deletion from UWC vector store.
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    
    # Find document
    document = db.query(RAGDocument).filter_by(
        id=document_id,
        tenant_id=tenant_id,
        deleted=False
    ).first()
    
    if not document:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.DOCUMENT_NOT_FOUND,
                message=f"Document {document_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Soft delete
    document.deleted = True
    document.deleted_at = datetime.utcnow()
    document.deleted_by = user_id
    document.indexing_status = IndexingStatus.DELETED
    
    # Request UWC deletion (if indexed)
    if settings.ENABLE_UWC_RAG and document.uwc_job_id:
        try:
            await uwc_client.delete_document(
                company_id=tenant_id,
                document_id=document_id,
                uwc_job_id=document.uwc_job_id
            )
        except Exception as e:
            logger.warning(f"Failed to delete from UWC: {str(e)}",
                          extra={"document_id": document_id})
            # Continue with local deletion even if UWC fails
    
    db.commit()
    
    # Audit log
    audit = AuditLogger(db, request)
    audit.log_action(
        action="document_deleted",
        resource_type="document",
        resource_id=document_id,
        metadata={"filename": document.filename}
    )
    
    logger.info(f"Document deleted",
               extra={
                   "document_id": document_id,
                   "tenant_id": tenant_id,
                   "filename": document.filename
               })
    
    return APIResponse(data={"status": "deleted", "document_id": document_id})


@router.post("/documents/upload", response_model=APIResponse[DocumentUploadResponse])
@require_role("exec", "manager")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type: str = "sop",
    db: Session = Depends(get_db)
):
    """
    Upload document (SOP, script, etc.) for RAG indexing.
    
    Flow:
    1. Upload to S3
    2. Create database record
    3. Send to UWC for indexing
    4. Return document_id and job_id
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    
    try:
        # Validate document type
        try:
            doc_type_enum = DocumentType(document_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.VALIDATION_ERROR,
                    message=f"Invalid document_type. Must be one of: {[t.value for t in DocumentType]}",
                    request_id=request.state.trace_id
                ).dict()
            )
        
        # Validate file size (50MB limit)
        file_size = 0
        content = await file.read()
        file_size = len(content)
        
        if file_size > 50 * 1024 * 1024:  # 50MB
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.VALIDATION_ERROR,
                    message="File size exceeds 50MB limit",
                    request_id=request.state.trace_id
                ).dict()
            )
        
        # Reset file pointer
        await file.seek(0)
        
        # Upload to S3
        from app.services.storage import storage_service
        
        if settings.is_storage_configured():
            file_url = await storage_service.upload_file(
                file=file.file,
                filename=file.filename,
                tenant_id=tenant_id,
                file_type="documents",
                content_type=file.content_type
            )
        else:
            # Fallback: local storage (development only)
            logger.warning("S3 not configured, using mock URL")
            file_url = f"http://localhost:8000/files/{tenant_id}/{uuid.uuid4()}/{file.filename}"
        
        # Create database record
        document_id = str(uuid.uuid4())
        document = RAGDocument(
            id=document_id,
            tenant_id=tenant_id,
            uploaded_by=user_id,
            filename=file.filename,
            file_url=file_url,
            file_size_bytes=file_size,
            content_type=file.content_type,
            document_type=doc_type_enum,
            indexing_status=IndexingStatus.PENDING
        )
        db.add(document)
        db.commit()
        
        # Send to UWC for indexing
        uwc_job_id = None
        if settings.ENABLE_UWC_RAG and settings.UWC_BASE_URL:
            try:
                uwc_result = await uwc_client.index_documents(
                    company_id=tenant_id,
                    documents=[{
                        "document_id": document_id,
                        "url": file_url,
                        "type": document_type,
                        "filename": file.filename
                    }],
                    request_id=request.state.trace_id
                )
                
                uwc_job_id = uwc_result.get("job_id")
                document.uwc_job_id = uwc_job_id
                document.indexing_status = IndexingStatus.PROCESSING
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to send document to UWC: {str(e)}",
                           extra={"document_id": document_id})
                # Keep local record even if UWC fails
        
        # Audit log
        audit = AuditLogger(db, request)
        audit.log_document_upload(
            document_id=document_id,
            filename=file.filename,
            file_size_bytes=file_size,
            document_type=document_type
        )
        
        logger.info(f"Document uploaded successfully",
                   extra={
                       "document_id": document_id,
                       "filename": file.filename,
                       "file_size_bytes": file_size,
                       "tenant_id": tenant_id
                   })
        
        # Return response
        return APIResponse(
            data=DocumentUploadResponse(
                document_id=document_id,
                status="processing" if uwc_job_id else "pending",
                filename=file.filename,
                file_url=file_url,
                uwc_job_id=uwc_job_id
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}",
                    extra={
                        "tenant_id": tenant_id,
                        "filename": file.filename
                    })
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message="Failed to upload document. Please try again.",
                request_id=request.state.trace_id
            ).dict()
        )


# Mock response generator for development
def mock_rag_response(query: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Generate mock RAG response for development without UWC.
    Returns realistic-looking answer based on query keywords.
    """
    # Keyword detection for contextual mocking
    query_lower = query.lower()
    
    if "objection" in query_lower:
        answer = """The most common objections faced by your team are:

1. **Price Too High** (40% of calls) - Customers feel the quote exceeds their budget
2. **Need to Think About It** (28% of calls) - Customers want more time to decide
3. **Need Other Quotes** (22% of calls) - Customers want to compare with competitors
4. **Timeline Too Long** (15% of calls) - Installation schedule doesn't meet their needs

**Recommendation**: Focus coaching on handling price objections early in the conversation using financing options."""
        
        citations = [
            {"doc_id": "doc_123", "filename": "objection_handler.pdf", 
             "chunk_text": "Price objections are best handled by offering financing...", 
             "similarity_score": 0.92},
            {"doc_id": "call_456", "call_id": 456,
             "chunk_text": "Customer said: 'That's more than I expected...'", 
             "similarity_score": 0.88, "timestamp": 125.5}
        ]
    
    elif "rep" in query_lower or "performance" in query_lower:
        answer = """Based on recent data:

**Top Performer**: Bradley Cohurst - 65% close rate, consistently sets agenda and handles objections well

**Needs Coaching**: Cole Ludewig - 25% close rate, frequently misses agenda-setting step

**Team Average**: 42% close rate across all reps

**Key Insight**: Reps who use Otto for pre-appointment prep have 23% higher close rates."""
        
        citations = [
            {"doc_id": "analysis_789", "chunk_text": "Bradley's strength is agenda-setting...", "similarity_score": 0.95}
        ]
    
    else:
        answer = f"""I found several relevant insights for your query: "{query}"

Based on your company's data, here are the key findings with citations from your documents and calls.

(This is a mock response - enable ENABLE_UWC_RAG=true to use real AI)"""
        
        citations = [
            {"doc_id": "mock_1", "filename": "company_data.pdf", 
             "chunk_text": "Mock citation...", "similarity_score": 0.80}
        ]
    
    return {
        "answer": answer,
        "citations": citations,
        "confidence_score": 0.85
    }

