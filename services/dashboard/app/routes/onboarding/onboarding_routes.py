"""
Onboarding API routes for multi-tenant company setup.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import json
import uuid

from app.database import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant import get_tenant_id
from app.schemas.onboarding import (
    CompanyBasicsRequest, CompanyBasicsResponse,
    CallRailConnectRequest, TwilioConnectRequest,
    CallTrackingConnectResponse, CallTrackingTestResponse,
    DocumentUploadRequest, DocumentUploadResponse, DocumentStatusResponse,
    GoalsPreferencesRequest, GoalsPreferencesResponse,
    InviteUserRequest, InviteUserResponse, InvitedUsersListResponse,
    VerificationRequest, VerificationResponse,
    OnboardingStatusResponse
)
from app.schemas.responses import APIResponse
from app.services.onboarding import (
    CompanyBasicsService,
    CallTrackingService,
    DocumentService,
    GoalsService,
    InvitationService,
    VerificationService
)
from app.tasks.onboarding_tasks import test_callrail_connection, test_twilio_connection
from app.obs.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


# Phase 1: Company Basics
@router.post(
    "/company-basics",
    response_model=APIResponse[CompanyBasicsResponse],
    summary="Save company basics information",
    description="Phase 1: Collect and save company basic information (name, phone, email, domain, industry, etc.)"
)
@require_role("manager")  # Only admins/managers can onboard
async def save_company_basics(
    request: Request,
    data: CompanyBasicsRequest,
    db: Session = Depends(get_db)
):
    """
    Save company basics information.
    
    This endpoint:
    - Validates company information
    - Saves to Company model
    - Moves onboarding_step to "call_tracking"
    - Is idempotent (safe to call multiple times)
    """
    tenant_id = get_tenant_id(request)
    user_id = request.state.user_id
    
    try:
        response, step_already_completed = CompanyBasicsService.save_company_basics(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            request=data
        )
        
        return APIResponse(data=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error saving company basics: {str(e)}",
            extra={"tenant_id": tenant_id, "user_id": user_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to save company basics")


# Phase 2: Call Tracking Integration
@router.post(
    "/callrail/connect",
    response_model=APIResponse[CallTrackingConnectResponse],
    summary="Connect CallRail account",
    description="Phase 2: Connect CallRail account for call tracking"
)
@require_role("manager")
async def connect_callrail(
    request: Request,
    data: CallRailConnectRequest,
    db: Session = Depends(get_db)
):
    """Connect CallRail account and configure webhooks."""
    tenant_id = get_tenant_id(request)
    user_id = request.state.user_id
    
    try:
        response, step_already_completed = CallTrackingService.connect_callrail(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            request=data
        )
        
        return APIResponse(data=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error connecting CallRail: {str(e)}",
            extra={"tenant_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to connect CallRail")


@router.post(
    "/twilio/connect",
    response_model=APIResponse[CallTrackingConnectResponse],
    summary="Connect Twilio account",
    description="Phase 2: Connect Twilio account for call tracking"
)
@require_role("manager")
async def connect_twilio(
    request: Request,
    data: TwilioConnectRequest,
    db: Session = Depends(get_db)
):
    """Connect Twilio account and configure webhooks."""
    tenant_id = get_tenant_id(request)
    user_id = request.state.user_id
    
    try:
        response, step_already_completed = CallTrackingService.connect_twilio(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            request=data
        )
        
        return APIResponse(data=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error connecting Twilio: {str(e)}",
            extra={"tenant_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to connect Twilio")


@router.post(
    "/callrail/test",
    response_model=APIResponse[CallTrackingTestResponse],
    summary="Test CallRail connection",
    description="Test CallRail API credentials before saving"
)
@require_role("manager")
async def test_callrail(
    request: Request,
    data: CallRailConnectRequest,
    db: Session = Depends(get_db)
):
    """Test CallRail connection without saving."""
    tenant_id = get_tenant_id(request)
    
    try:
        # Queue async test task
        task = test_callrail_connection.delay(
            company_id=tenant_id,
            api_key=data.api_key,
            account_id=data.account_id
        )
        
        # Wait for result (with timeout)
        result = task.get(timeout=15)
        
        return APIResponse(data={
            "success": result.get("status") == "success",
            "connected": result.get("connected", False),
            "webhook_url": CallTrackingService._get_callrail_webhook_url(),
            "message": result.get("account_name") or result.get("error", "Connection test completed")
        })
    except Exception as e:
        logger.error(
            f"CallRail test failed: {str(e)}",
            extra={"tenant_id": tenant_id},
            exc_info=True
        )
        return APIResponse(data={
            "success": False,
            "connected": False,
            "webhook_url": CallTrackingService._get_callrail_webhook_url(),
            "message": f"Connection test failed: {str(e)}"
        })


@router.post(
    "/twilio/test",
    response_model=APIResponse[CallTrackingTestResponse],
    summary="Test Twilio connection",
    description="Test Twilio API credentials before saving"
)
@require_role("manager")
async def test_twilio(
    request: Request,
    data: TwilioConnectRequest,
    db: Session = Depends(get_db)
):
    """Test Twilio connection without saving."""
    tenant_id = get_tenant_id(request)
    
    try:
        # Queue async test task
        task = test_twilio_connection.delay(
            company_id=tenant_id,
            account_sid=data.account_sid,
            auth_token=data.auth_token
        )
        
        # Wait for result (with timeout)
        result = task.get(timeout=15)
        
        return APIResponse(data={
            "success": result.get("status") == "success",
            "connected": result.get("connected", False),
            "webhook_url": CallTrackingService._get_twilio_webhook_url(),
            "message": result.get("account_name") or result.get("error", "Connection test completed")
        })
    except Exception as e:
        logger.error(
            f"Twilio test failed: {str(e)}",
            extra={"tenant_id": tenant_id},
            exc_info=True
        )
        return APIResponse(data={
            "success": False,
            "connected": False,
            "webhook_url": CallTrackingService._get_twilio_webhook_url(),
            "message": f"Connection test failed: {str(e)}"
        })


# Phase 3: Document Upload & Ingestion
@router.post(
    "/documents/upload",
    response_model=APIResponse[DocumentUploadResponse],
    summary="Upload document for ingestion",
    description="Phase 3: Upload company documents (SOPs, training materials, etc.) for Shunya ingestion"
)
@require_role("manager")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(...),
    role_target: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),  # JSON string
    db: Session = Depends(get_db)
):
    """
    Upload document for ingestion.
    
    Files are uploaded to S3, then a Celery task sends them to Shunya for processing.
    """
    tenant_id = get_tenant_id(request)
    user_id = request.state.user_id
    trace_id = getattr(request.state, 'trace_id', str(uuid.uuid4()))
    
    # Parse metadata if provided
    metadata_dict = None
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid metadata JSON")
    
    # Create request object
    upload_request = DocumentUploadRequest(
        category=category,
        role_target=role_target,
        metadata=metadata_dict
    )
    
    try:
        service = DocumentService()
        response = await service.upload_document(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            file=file,
            request=upload_request,
            trace_id=trace_id
        )
        
        return APIResponse(data=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error uploading document: {str(e)}",
            extra={"tenant_id": tenant_id, "file_name": file.filename},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to upload document")


@router.get(
    "/documents/status/{document_id}",
    response_model=APIResponse[DocumentStatusResponse],
    summary="Get document ingestion status",
    description="Check the status of a document ingestion job"
)
@require_role("manager", "csr", "sales_rep")
async def get_document_status(
    request: Request,
    document_id: str,
    db: Session = Depends(get_db)
):
    """Get document ingestion status."""
    tenant_id = get_tenant_id(request)
    
    try:
        service = DocumentService()
        response = service.get_document_status(
            db=db,
            tenant_id=tenant_id,
            document_id=document_id
        )
        
        return APIResponse(data=response)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error getting document status: {str(e)}",
            extra={"tenant_id": tenant_id, "document_id": document_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to get document status")


# Phase 4: Goals & Preferences
@router.post(
    "/goals",
    response_model=APIResponse[GoalsPreferencesResponse],
    summary="Save goals and preferences",
    description="Phase 4: Save company goals, KPIs, and notification preferences"
)
@require_role("manager")
async def save_goals_preferences(
    request: Request,
    data: GoalsPreferencesRequest,
    db: Session = Depends(get_db)
):
    """Save goals and preferences."""
    tenant_id = get_tenant_id(request)
    user_id = request.state.user_id
    
    try:
        response, step_already_completed = GoalsService.save_goals_preferences(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            request=data
        )
        
        return APIResponse(data=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error saving goals: {str(e)}",
            extra={"tenant_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to save goals and preferences")


# Phase 5: Team Invitations
@router.post(
    "/invite-user",
    response_model=APIResponse[InviteUserResponse],
    summary="Invite team member",
    description="Phase 5: Invite a team member (CSR, sales rep, or manager) via Clerk"
)
@require_role("manager")
async def invite_user(
    request: Request,
    data: InviteUserRequest,
    db: Session = Depends(get_db)
):
    """Invite a user to the organization."""
    tenant_id = get_tenant_id(request)
    user_id = request.state.user_id
    
    try:
        service = InvitationService()
        response = await service.invite_user(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            request=data
        )
        
        return APIResponse(data=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error inviting user: {str(e)}",
            extra={"tenant_id": tenant_id, "email": data.email},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to send invitation")


@router.get(
    "/invited-users",
    response_model=APIResponse[InvitedUsersListResponse],
    summary="List invited users",
    description="Get list of all invited users and their status"
)
@require_role("manager")
async def get_invited_users(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get list of invited users."""
    tenant_id = get_tenant_id(request)
    
    try:
        service = InvitationService()
        response = service.get_invited_users(
            db=db,
            tenant_id=tenant_id
        )
        
        return APIResponse(data=response)
    except Exception as e:
        logger.error(
            f"Error getting invited users: {str(e)}",
            extra={"tenant_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to get invited users")


# Phase 6: Final Verification
@router.post(
    "/verify",
    response_model=APIResponse[VerificationResponse],
    summary="Verify and complete onboarding",
    description="Phase 6: Verify all onboarding steps are complete and mark onboarding as done"
)
@require_role("manager")
async def verify_onboarding(
    request: Request,
    data: VerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Verify onboarding completion.
    
    Checks:
    - Company basics completed
    - Call tracking configured
    - Documents ingested
    - At least 1 CSR or sales rep exists
    
    If all checks pass, marks onboarding as complete.
    """
    tenant_id = get_tenant_id(request)
    user_id = request.state.user_id
    
    try:
        response = VerificationService.verify_and_complete(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        return APIResponse(data=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Error verifying onboarding: {str(e)}",
            extra={"tenant_id": tenant_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to verify onboarding")


# Status & Progress
@router.get(
    "/status",
    response_model=APIResponse[OnboardingStatusResponse],
    summary="Get onboarding status",
    description="Get current onboarding status and progress"
)
@require_role("manager", "csr", "sales_rep")
async def get_onboarding_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get onboarding status and progress."""
    tenant_id = get_tenant_id(request)
    
    from app.models import company as company_model
    from app.models.onboarding import Document, IngestionStatus
    from app.models import user as user_model
    
    company = db.query(company_model.Company).filter_by(id=tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Calculate progress
    progress = {
        "company_basics": company.onboarding_step != "company_basics",
        "call_tracking": company.call_provider is not None,
        "documents": db.query(Document).filter_by(
            company_id=tenant_id,
            ingestion_status=IngestionStatus.DONE
        ).count() > 0,
        "goals_preferences": company.onboarding_step not in ["company_basics", "call_tracking", "document_ingestion"],
        "team_invites": db.query(user_model.User).filter_by(
            company_id=tenant_id
        ).filter(
            user_model.User.role.in_(["csr", "sales_rep"])
        ).count() > 0
    }
    
    return APIResponse(data={
        "company_id": tenant_id,
        "onboarding_step": company.onboarding_step,
        "onboarding_completed": company.onboarding_completed,
        "onboarding_completed_at": company.onboarding_completed_at,
        "progress": progress
    })

