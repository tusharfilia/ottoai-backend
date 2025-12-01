"""
Service for handling final onboarding verification step.
"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import company as company_model
from app.models.onboarding import OnboardingEvent, Document, IngestionStatus
from app.models import user as user_model
from app.obs.logging import get_logger

logger = get_logger(__name__)


class VerificationService:
    """Service for final onboarding verification."""
    
    @staticmethod
    def verify_and_complete(
        db: Session,
        tenant_id: str,
        user_id: str
    ) -> dict:
        """
        Verify all onboarding steps are complete and mark onboarding as done.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID
            user_id: User ID
            
        Returns:
            Verification response
        """
        company = db.query(company_model.Company).filter_by(id=tenant_id).first()
        if not company:
            raise ValueError(f"Company not found: {tenant_id}")
        
        # Run verification checks
        checks = {
            "company_basics": VerificationService._check_company_basics(company),
            "call_tracking": VerificationService._check_call_tracking(company),
            "documents": VerificationService._check_documents(db, tenant_id),
            "team_members": VerificationService._check_team_members(db, tenant_id)
        }
        
        all_passed = all(checks.values())
        errors = []
        
        if not checks["company_basics"]:
            errors.append("Company basics not completed")
        if not checks["call_tracking"]:
            errors.append("Call tracking not configured")
        if not checks["documents"]:
            errors.append("No documents uploaded or documents still processing")
        if not checks["team_members"]:
            errors.append("No team members (CSR or sales rep) added")
        
        if all_passed:
            # Mark onboarding as complete
            company.onboarding_completed = True
            company.onboarding_completed_at = datetime.utcnow()
            company.onboarding_step = "completed"
            
            # Log event
            event = OnboardingEvent(
                id=str(uuid.uuid4()),
                company_id=tenant_id,
                user_id=user_id,
                step="verification",
                action="completed",
                metadata={"checks": checks}
            )
            db.add(event)
            
            db.commit()
            db.refresh(company)
            
            logger.info(
                f"Onboarding completed for company {tenant_id}",
                extra={"tenant_id": tenant_id, "user_id": user_id}
            )
        else:
            # Log verification failure
            event = OnboardingEvent(
                id=str(uuid.uuid4()),
                company_id=tenant_id,
                user_id=user_id,
                step="verification",
                action="failed",
                metadata={"checks": checks, "errors": errors}
            )
            db.add(event)
            db.commit()
            
            logger.warning(
                f"Onboarding verification failed for company {tenant_id}",
                extra={"tenant_id": tenant_id, "checks": checks, "errors": errors}
            )
        
        return {
            "success": all_passed,
            "onboarding_completed": all_passed,
            "onboarding_completed_at": company.onboarding_completed_at if all_passed else None,
            "checks": checks,
            "errors": errors
        }
    
    @staticmethod
    def _check_company_basics(company: company_model.Company) -> bool:
        """Check if company basics are complete."""
        return bool(
            company.name and
            company.phone_number and
            company.industry and
            company.timezone
        )
    
    @staticmethod
    def _check_call_tracking(company: company_model.Company) -> bool:
        """Check if call tracking is configured."""
        if company.call_provider == company_model.CallProvider.CALLRAIL:
            return bool(company.callrail_api_key and company.callrail_account_id)
        elif company.call_provider == company_model.CallProvider.TWILIO:
            return bool(company.twilio_account_sid and company.twilio_auth_token)
        return False
    
    @staticmethod
    def _check_documents(db: Session, tenant_id: str) -> bool:
        """Check if at least one document is uploaded and processed."""
        # Check if any documents exist
        doc_count = db.query(Document).filter_by(company_id=tenant_id).count()
        if doc_count == 0:
            return False
        
        # Check if at least one document is done (not pending or processing)
        done_docs = db.query(Document).filter_by(
            company_id=tenant_id
        ).filter(
            Document.ingestion_status == IngestionStatus.DONE
        ).count()
        
        return done_docs > 0
    
    @staticmethod
    def _check_team_members(db: Session, tenant_id: str) -> bool:
        """Check if at least one CSR or sales rep exists."""
        csr_count = db.query(user_model.User).filter_by(
            company_id=tenant_id,
            role="csr"
        ).count()
        
        rep_count = db.query(user_model.User).filter_by(
            company_id=tenant_id,
            role="sales_rep"
        ).count()
        
        return (csr_count + rep_count) > 0

