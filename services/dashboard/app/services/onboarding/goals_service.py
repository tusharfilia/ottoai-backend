"""
Service for handling goals and preferences onboarding step.
"""
import uuid
import json
from sqlalchemy.orm import Session
from app.models import company as company_model
from app.models.onboarding import OnboardingEvent
from app.obs.logging import get_logger
from app.schemas.onboarding import GoalsPreferencesRequest

logger = get_logger(__name__)


class GoalsService:
    """Service for goals and preferences step."""
    
    @staticmethod
    def save_goals_preferences(
        db: Session,
        tenant_id: str,
        user_id: str,
        request: GoalsPreferencesRequest
    ) -> tuple[dict, bool]:
        """
        Save goals and preferences.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID
            user_id: User ID
            request: Goals and preferences request
            
        Returns:
            Tuple of (response_dict, step_already_completed)
        """
        company = db.query(company_model.Company).filter_by(id=tenant_id).first()
        if not company:
            raise ValueError(f"Company not found: {tenant_id}")
        
        # Check if step already completed
        step_already_completed = (
            company.onboarding_step != "goals_preferences" and
            company.onboarding_step not in ["goals_preferences", "team_invites", "verification"]
        )
        
        if step_already_completed:
            logger.info(
                f"Goals and preferences already saved for company {tenant_id}",
                extra={"tenant_id": tenant_id, "current_step": company.onboarding_step}
            )
            return {
                "success": True,
                "onboarding_step": company.onboarding_step,
                "step_already_completed": True
            }, True
        
        # Store goals and preferences in company metadata (could use a separate table in future)
        # For now, we'll store in a JSON field if we add one, or use existing fields
        # Since we don't have a preferences_json field on Company, we'll log it in the event metadata
        
        # Move to next step
        company.onboarding_step = "team_invites"
        
        # Log event with goals data
        event = OnboardingEvent(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            user_id=user_id,
            step="goals_preferences",
            action="completed",
            metadata={
                "primary_goals": request.primary_goals,
                "target_metrics": request.target_metrics,
                "notification_preferences": request.notification_preferences,
                "quiet_hours": {
                    "start": request.quiet_hours_start,
                    "end": request.quiet_hours_end
                } if request.quiet_hours_start else None
            }
        )
        db.add(event)
        
        db.commit()
        db.refresh(company)
        
        logger.info(
            f"Goals and preferences saved for company {tenant_id}",
            extra={"tenant_id": tenant_id, "user_id": user_id}
        )
        
        return {
            "success": True,
            "onboarding_step": company.onboarding_step,
            "step_already_completed": False
        }, False

