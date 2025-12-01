"""
Service for handling team invitations onboarding step.
"""
import uuid
import httpx
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import company as company_model
from app.models.onboarding import OnboardingEvent
from app.config import settings
from app.obs.logging import get_logger
from app.schemas.onboarding import InviteUserRequest

logger = get_logger(__name__)


class InvitationService:
    """Service for team invitations."""
    
    @staticmethod
    async def invite_user(
        db: Session,
        tenant_id: str,
        user_id: str,
        request: InviteUserRequest
    ) -> dict:
        """
        Invite a user to the organization via Clerk.
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID (Clerk org ID)
            user_id: User ID who is sending the invite
            request: Invite user request
            
        Returns:
            Invite response
        """
        company = db.query(company_model.Company).filter_by(id=tenant_id).first()
        if not company:
            raise ValueError(f"Company not found: {tenant_id}")
        
        # Map role to Clerk role
        role_mapping = {
            "manager": "org:admin",
            "csr": "org:member",
            "sales_rep": "org:member"
        }
        clerk_role = role_mapping.get(request.role, "org:member")
        
        # Call Clerk API to create organization invitation
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.CLERK_API_URL}/organizations/{tenant_id}/invitations",
                    headers={
                        "Authorization": f"Bearer {settings.CLERK_SECRET_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "email_address": request.email,
                        "role": clerk_role
                    }
                )
                response.raise_for_status()
                invite_data = response.json()
                
                logger.info(
                    f"Invitation sent via Clerk for {request.email}",
                    extra={
                        "tenant_id": tenant_id,
                        "email": request.email,
                        "role": request.role,
                        "clerk_invite_id": invite_data.get("id")
                    }
                )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Clerk API error sending invitation: {e.response.text}",
                extra={"tenant_id": tenant_id, "email": request.email}
            )
            raise ValueError(f"Failed to send invitation: {e.response.text}")
        except Exception as e:
            logger.error(
                f"Error sending invitation: {str(e)}",
                extra={"tenant_id": tenant_id, "email": request.email}
            )
            raise ValueError(f"Failed to send invitation: {str(e)}")
        
        # Log event
        event = OnboardingEvent(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            user_id=user_id,
            step="team_invites",
            action="invite_sent",
            metadata={
                "email": request.email,
                "role": request.role,
                "territory": request.territory,
                "department": request.department,
                "clerk_invite_id": invite_data.get("id")
            }
        )
        db.add(event)
        db.commit()
        
        return {
            "success": True,
            "invite_id": invite_data.get("id", str(uuid.uuid4())),
            "email": request.email,
            "role": request.role,
            "status": "sent"
        }
    
    @staticmethod
    def get_invited_users(
        db: Session,
        tenant_id: str
    ) -> dict:
        """
        Get list of invited users (from onboarding events).
        
        Args:
            db: Database session
            tenant_id: Tenant/company ID
            
        Returns:
            List of invited users
        """
        # Get all invite events for this company
        events = db.query(OnboardingEvent).filter_by(
            company_id=tenant_id,
            step="team_invites",
            action="invite_sent"
        ).order_by(OnboardingEvent.timestamp.desc()).all()
        
        invited_users = []
        for event in events:
            metadata = event.metadata_json or {}
            invited_users.append({
                "invite_id": event.id,
                "email": metadata.get("email"),
                "role": metadata.get("role"),
                "territory": metadata.get("territory"),
                "status": "pending",  # Could be enhanced with Clerk status check
                "invited_at": event.timestamp,
                "accepted_at": None  # Could be enhanced with Clerk webhook data
            })
        
        return {
            "invited_users": invited_users,
            "total": len(invited_users)
        }

