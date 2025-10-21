"""
Audit logging service for security and compliance.
Provides simple interface for logging sensitive operations.
"""
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import Request

from app.models.audit_log import AuditLog
from app.obs.logging import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """
    Service for logging audit events.
    
    Usage:
        audit = AuditLogger(db, request)
        audit.log_action(
            action="user_created",
            resource_type="user",
            resource_id=user.id,
            changes={"email": user.email, "role": user.role}
        )
    """
    
    def __init__(self, db: Session, request: Optional[Request] = None):
        """
        Initialize audit logger.
        
        Args:
            db: Database session
            request: FastAPI request object (for context extraction)
        """
        self.db = db
        self.request = request
    
    def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        success: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        """
        Log an audit event.
        
        Args:
            action: Action performed (e.g., "user_created", "document_uploaded")
            resource_type: Type of resource (e.g., "user", "document", "call")
            resource_id: ID of the resource
            tenant_id: Company ID (extracted from request if not provided)
            user_id: User who performed action (extracted from request if not provided)
            changes: What changed (e.g., {"role": "manager → exec"})
            metadata: Additional context
            success: "success", "failure", or "partial"
            error_message: Error message if action failed
        
        Returns:
            Created audit log entry
        """
        # Extract context from request if available
        if self.request:
            if not tenant_id:
                tenant_id = getattr(self.request.state, 'tenant_id', None)
            if not user_id:
                user_id = getattr(self.request.state, 'user_id', None)
            
            ip_address = self._get_client_ip()
            user_agent = self.request.headers.get('user-agent')
            request_id = getattr(self.request.state, 'trace_id', None)
        else:
            ip_address = None
            user_agent = None
            request_id = None
        
        # Create audit log entry
        audit_log = AuditLog(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            success=success,
            error_message=error_message
        )
        
        # Save to database
        try:
            self.db.add(audit_log)
            self.db.commit()
            
            logger.info(f"Audit log created",
                       extra={
                           "audit_id": audit_log.id,
                           "action": action,
                           "resource_type": resource_type,
                           "resource_id": resource_id,
                           "tenant_id": tenant_id,
                           "user_id": user_id
                       })
            
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}",
                        extra={
                            "action": action,
                            "resource_type": resource_type,
                            "resource_id": resource_id
                        })
            self.db.rollback()
            raise
    
    def log_rag_query(
        self,
        query_text: str,
        answer_text: str,
        confidence_score: Optional[float] = None,
        result_count: int = 0
    ):
        """
        Log Ask Otto query for audit trail.
        
        Args:
            query_text: The question asked
            answer_text: Otto's response
            confidence_score: Query confidence
            result_count: Number of results returned
        """
        return self.log_action(
            action="rag_query",
            resource_type="rag_query",
            resource_id=str(uuid.uuid4()),  # Generate ID for query
            metadata={
                "query": query_text,
                "answer_preview": answer_text[:200] if answer_text else None,
                "confidence_score": confidence_score,
                "result_count": result_count
            }
        )
    
    def log_document_upload(
        self,
        document_id: str,
        filename: str,
        file_size_bytes: int,
        document_type: str
    ):
        """Log document upload for compliance."""
        return self.log_action(
            action="document_uploaded",
            resource_type="document",
            resource_id=document_id,
            metadata={
                "filename": filename,
                "file_size_bytes": file_size_bytes,
                "document_type": document_type
            }
        )
    
    def log_user_deletion(
        self,
        deleted_user_id: str,
        deleted_email: str,
        reason: str = "gdpr_request"
    ):
        """Log user deletion (critical for GDPR compliance)."""
        return self.log_action(
            action="user_deleted",
            resource_type="user",
            resource_id=deleted_user_id,
            metadata={
                "email": deleted_email,
                "reason": reason
            }
        )
    
    def log_role_change(
        self,
        target_user_id: str,
        old_role: str,
        new_role: str
    ):
        """Log role changes for security audit."""
        return self.log_action(
            action="role_changed",
            resource_type="user",
            resource_id=target_user_id,
            changes={
                "old_role": old_role,
                "new_role": new_role
            }
        )
    
    def log_settings_change(
        self,
        setting_name: str,
        old_value: Any,
        new_value: Any
    ):
        """Log company settings changes."""
        return self.log_action(
            action="settings_changed",
            resource_type="company_settings",
            resource_id=setting_name,
            changes={
                "old_value": str(old_value),
                "new_value": str(new_value)
            }
        )
    
    def _get_client_ip(self) -> Optional[str]:
        """Extract client IP address from request."""
        if not self.request:
            return None
        
        # Check X-Forwarded-For header (for proxied requests)
        forwarded = self.request.headers.get('x-forwarded-for')
        if forwarded:
            # Take first IP if multiple
            return forwarded.split(',')[0].strip()
        
        # Fall back to direct connection IP
        if self.request.client:
            return self.request.client.host
        
        return None


def log_audit_event(
    db: Session,
    request: Request,
    action: str,
    resource_type: str,
    resource_id: str,
    **kwargs
) -> AuditLog:
    """
    Convenience function for logging audit events.
    
    Usage:
        log_audit_event(
            db=db,
            request=request,
            action="user_created",
            resource_type="user",
            resource_id=user.id,
            metadata={"email": user.email}
        )
    """
    audit = AuditLogger(db, request)
    return audit.log_action(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        **kwargs
    )



