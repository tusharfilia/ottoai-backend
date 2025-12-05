"""
Service for handling company basics onboarding step.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models import company as company_model
from app.models import user as user_model
from app.models.onboarding import OnboardingEvent
from app.obs.logging import get_logger
from app.schemas.onboarding import CompanyBasicsRequest

logger = get_logger(__name__)


class CompanyBasicsService:
    """Service for company basics onboarding step."""
    
    @staticmethod
    def save_company_basics(
        db: Session,
        tenant_id: str,
        user_id: str,
        request: CompanyBasicsRequest
    ) -> tuple[dict, bool]:
        """
        Save company basics information.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID from JWT
            user_id: User ID from JWT
            request: Company basics request data
            
        Returns:
            Tuple of (response_dict, step_already_completed)
        """
        # Load company (must exist - created during Clerk org creation or lazy creation)
        company = db.query(company_model.Company).filter_by(id=tenant_id).first()
        if not company:
            raise ValueError(f"Company not found for tenant_id: {tenant_id}")
        
        # Check if step already completed
        step_already_completed = (
            company.onboarding_step != "company_basics" and
            company.onboarding_step is not None
        )
        
        if step_already_completed:
            logger.info(
                f"Company basics step already completed for company {tenant_id}",
                extra={"tenant_id": tenant_id, "current_step": company.onboarding_step}
            )
            return {
                "success": True,
                "company_id": tenant_id,
                "onboarding_step": company.onboarding_step,
                "step_already_completed": True
            }, True
        
        # Update company fields (idempotent - safe to call multiple times)
        company.name = request.company_name
        company.phone_number = request.company_phone
        company.industry = request.industry
        company.timezone = request.timezone
        company.domain = request.company_domain
        company.domain_verified = False  # Will be verified in final step
        
        # Update address if provided
        if request.company_address:
            company.address = request.company_address
        
        # Move to next step
        company.onboarding_step = "call_tracking"
        
        # Update admin user if exists
        admin_user = db.query(user_model.User).filter_by(id=user_id).first()
        if admin_user:
            admin_user.name = request.admin_name
            admin_user.email = request.admin_email
            if not admin_user.role:
                admin_user.role = "manager"
        
        # Log onboarding event
        event = OnboardingEvent(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            user_id=user_id,
            step="company_basics",
            action="completed",
            metadata={
                "company_name": request.company_name,
                "industry": request.industry,
                "team_size": request.team_size
            }
        )
        db.add(event)
        
        db.commit()
        db.refresh(company)
        
        logger.info(
            f"Company basics saved for company {tenant_id}",
            extra={"tenant_id": tenant_id, "user_id": user_id}
        )
        
        return {
            "success": True,
            "company_id": tenant_id,
            "onboarding_step": company.onboarding_step,
            "step_already_completed": False
        }, False




