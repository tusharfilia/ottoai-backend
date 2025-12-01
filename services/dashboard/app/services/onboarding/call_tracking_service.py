"""
Service for handling call tracking integration onboarding step.
"""
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.models import company as company_model
from app.models.onboarding import OnboardingEvent
from app.config import settings
from app.obs.logging import get_logger
from app.schemas.onboarding import CallRailConnectRequest, TwilioConnectRequest

logger = get_logger(__name__)


class CallTrackingService:
    """Service for call tracking integration step."""
    
    @staticmethod
    def connect_callrail(
        db: Session,
        tenant_id: str,
        user_id: str,
        request: CallRailConnectRequest
    ) -> tuple[dict, bool]:
        """
        Connect CallRail account.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID
            user_id: User ID
            request: CallRail connection request
            
        Returns:
            Tuple of (response_dict, step_already_completed)
        """
        company = db.query(company_model.Company).filter_by(id=tenant_id).first()
        if not company:
            raise ValueError(f"Company not found: {tenant_id}")
        
        # Check if step already completed
        step_already_completed = (
            company.onboarding_step != "call_tracking" and
            company.call_provider is not None
        )
        
        if step_already_completed:
            logger.info(
                f"Call tracking already configured for company {tenant_id}",
                extra={"tenant_id": tenant_id, "provider": company.call_provider}
            )
            return {
                "success": True,
                "provider": company.call_provider.value if company.call_provider else None,
                "onboarding_step": company.onboarding_step,
                "webhook_url": CallTrackingService._get_callrail_webhook_url(),
                "step_already_completed": True
            }, True
        
        # Store CallRail credentials
        company.callrail_api_key = request.api_key
        company.callrail_account_id = request.account_id
        company.call_provider = company_model.CallProvider.CALLRAIL
        
        if request.primary_tracking_number:
            company.primary_tracking_number = request.primary_tracking_number
        
        # Move to next step
        company.onboarding_step = "document_ingestion"
        
        # Log event
        event = OnboardingEvent(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            user_id=user_id,
            step="call_tracking",
            action="completed",
            metadata={"provider": "callrail"}
        )
        db.add(event)
        
        db.commit()
        db.refresh(company)
        
        logger.info(
            f"CallRail connected for company {tenant_id}",
            extra={"tenant_id": tenant_id, "user_id": user_id}
        )
        
        return {
            "success": True,
            "provider": "callrail",
            "onboarding_step": company.onboarding_step,
            "webhook_url": CallTrackingService._get_callrail_webhook_url(),
            "step_already_completed": False
        }, False
    
    @staticmethod
    def connect_twilio(
        db: Session,
        tenant_id: str,
        user_id: str,
        request: TwilioConnectRequest
    ) -> tuple[dict, bool]:
        """
        Connect Twilio account.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID
            user_id: User ID
            request: Twilio connection request
            
        Returns:
            Tuple of (response_dict, step_already_completed)
        """
        company = db.query(company_model.Company).filter_by(id=tenant_id).first()
        if not company:
            raise ValueError(f"Company not found: {tenant_id}")
        
        # Check if step already completed
        step_already_completed = (
            company.onboarding_step != "call_tracking" and
            company.call_provider is not None
        )
        
        if step_already_completed:
            logger.info(
                f"Call tracking already configured for company {tenant_id}",
                extra={"tenant_id": tenant_id, "provider": company.call_provider}
            )
            return {
                "success": True,
                "provider": company.call_provider.value if company.call_provider else None,
                "onboarding_step": company.onboarding_step,
                "webhook_url": CallTrackingService._get_twilio_webhook_url(),
                "step_already_completed": True
            }, True
        
        # Store Twilio credentials
        company.twilio_account_sid = request.account_sid
        company.twilio_auth_token = request.auth_token
        company.call_provider = company_model.CallProvider.TWILIO
        company.primary_tracking_number = request.primary_tracking_number
        
        # Move to next step
        company.onboarding_step = "document_ingestion"
        
        # Log event
        event = OnboardingEvent(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            user_id=user_id,
            step="call_tracking",
            action="completed",
            metadata={"provider": "twilio"}
        )
        db.add(event)
        
        db.commit()
        db.refresh(company)
        
        logger.info(
            f"Twilio connected for company {tenant_id}",
            extra={"tenant_id": tenant_id, "user_id": user_id}
        )
        
        return {
            "success": True,
            "provider": "twilio",
            "onboarding_step": company.onboarding_step,
            "webhook_url": CallTrackingService._get_twilio_webhook_url(),
            "step_already_completed": False
        }, False
    
    @staticmethod
    def _get_callrail_webhook_url() -> str:
        """Get CallRail webhook URL."""
        from app.config import settings
        base_url = settings.BACKEND_URL
        return f"{base_url}/callrail/call.completed"
    
    @staticmethod
    def _get_twilio_webhook_url() -> str:
        """Get Twilio webhook URL."""
        from app.config import settings
        base_url = settings.BACKEND_URL
        return f"{base_url}/mobile/twilio-voice-webhook"

