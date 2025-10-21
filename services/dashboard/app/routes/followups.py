"""
Follow-Up endpoints for AI-generated follow-up messages.
Supports SMS, email, and call script generation with quiet hours enforcement.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import pytz

from app.database import get_db
from app.middleware.rbac import require_role
from app.config import settings
from app.services.uwc_client import get_uwc_client
from app.services.audit_logger import AuditLogger
from app.models.call import Call
from app.models.followup_draft import FollowUpDraft, DraftType, DraftStatus
from app.models.company import Company
from app.schemas.responses import APIResponse, PaginatedResponse, PaginationMeta, ErrorResponse, ErrorCodes, create_error_response
from app.obs.logging import get_logger
from app.obs.metrics import metrics

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/followups", tags=["followups", "ai-messaging"])


# Request/Response Schemas
class GenerateDraftRequest(BaseModel):
    """Request to generate follow-up draft."""
    call_id: int = Field(..., description="Call to generate follow-up for")
    draft_type: str = Field("sms", description="Type of draft: sms, email, call_script")
    tone: Optional[str] = Field("professional", description="Tone: professional, friendly, urgent")
    use_personal_clone: bool = Field(True, description="Use rep's personal clone if available")
    
    class Config:
        json_schema_extra = {
            "example": {
                "call_id": 123,
                "draft_type": "sms",
                "tone": "friendly",
                "use_personal_clone": True
            }
        }


class DraftResponse(BaseModel):
    """Follow-up draft response."""
    draft_id: str
    call_id: int
    draft_text: str
    draft_type: str
    tone: str
    status: str
    blocked_by_quiet_hours: bool = False
    scheduled_send_time: Optional[str] = None
    generated_by: str  # "personal_clone" or "generic_ai"


# Endpoints

@router.post("/draft", response_model=APIResponse[DraftResponse])
@require_role("admin", "rep")
async def generate_followup_draft(
    request: Request,
    draft_request: GenerateDraftRequest,
    db: Session = Depends(get_db)
):
    """
    Generate AI follow-up draft using personal clone or generic AI.
    
    Features:
    - Personal clone (rep's style) if available
    - Quiet hours enforcement (9PM-8AM local time)
    - Automatic scheduling if in quiet hours
    - Draft approval workflow (human-in-loop)
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    user_role = request.state.user_role
    
    # Validate draft type
    try:
        draft_type_enum = DraftType(draft_request.draft_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message=f"Invalid draft_type. Must be one of: {[t.value for t in DraftType]}",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Get call and verify access
    call = db.query(Call).filter_by(
        call_id=draft_request.call_id,
        company_id=tenant_id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.CALL_NOT_FOUND,
                message=f"Call {draft_request.call_id} not found",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Reps can only generate for their own calls
    if user_role == "rep" and call.assigned_rep_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=create_error_response(
                error_code=ErrorCodes.FORBIDDEN,
                message="You can only generate follow-ups for your own calls",
                request_id=request.state.trace_id
            ).dict()
        )
    
    # Check quiet hours (9PM-8AM local time)
    quiet_hours_check = check_quiet_hours(call.phone_number, tenant_id, db)
    
    # If in quiet hours, schedule for later
    scheduled_send_time = None
    if quiet_hours_check['is_blocked']:
        scheduled_send_time = quiet_hours_check['next_available_time']
        logger.info(f"Draft blocked by quiet hours, scheduled for {scheduled_send_time}",
                   extra={"call_id": call.call_id, "phone": call.phone_number})
    
    try:
        # Try UWC follow-up generation first if enabled
        draft_text = None
        generated_by = "generic_ai"
        
        if settings.ENABLE_UWC_FOLLOWUPS and settings.UWC_BASE_URL:
            try:
                # Prepare context for AI generation
                context = {
                    "customer_name": call.name,
                    "call_summary": call.transcript or "",
                    "call_date": call.created_at.isoformat() if call.created_at else None,
                    "objections": [],  # Could pull from call_analysis if available
                    "rep_name": "Rep",  # Could pull from user table
                    "company_name": tenant_id
                }
                
                logger.info(f"Attempting UWC follow-up generation for call {call.call_id}")
                uwc_client = get_uwc_client()
                uwc_result = await uwc_client.generate_followup_draft(
                    company_id=tenant_id,
                    request_id=request.state.trace_id,
                    rep_id=call.assigned_rep_id or user_id,
                    call_context=context,
                    draft_type=draft_request.draft_type,
                    tone=draft_request.tone,
                    options={
                        "use_personal_clone": draft_request.use_personal_clone,
                        "max_length": 160 if draft_request.draft_type == "sms" else 500
                    }
                )
                
                draft_text = uwc_result.get("draft_text", "")
                if draft_text:
                    generated_by = "personal_clone" if uwc_result.get("used_clone") else "generic_ai"
                    logger.info(f"UWC follow-up generation successful for call {call.call_id}")
                else:
                    raise Exception("UWC follow-up generation returned empty draft")
                    
            except Exception as e:
                logger.warning(f"UWC follow-up generation failed for call {call.call_id}, falling back to mock: {str(e)}")
                # Fall through to mock fallback
        
        # Fallback to mock generation if UWC is disabled or failed
        if not draft_text:
            logger.info(f"Using mock follow-up generation for call {call.call_id}")
            draft_text = generate_mock_draft(call, draft_request.draft_type, draft_request.tone)
        
        # Save draft to database
        draft_id = str(uuid.uuid4())
        draft = FollowUpDraft(
            id=draft_id,
            tenant_id=tenant_id,
            call_id=call.call_id,
            generated_for=call.assigned_rep_id or user_id,
            generated_by=generated_by,
            draft_text=draft_text,
            draft_type=draft_type_enum,
            tone=draft_request.tone,
            status=DraftStatus.PENDING,
            blocked_by_quiet_hours=quiet_hours_check['is_blocked'],
            scheduled_send_time=scheduled_send_time,
            expires_at=datetime.utcnow() + timedelta(days=7)  # Drafts expire after 7 days
        )
        db.add(draft)
        db.commit()
        
        logger.info(f"Follow-up draft generated",
                   extra={
                       "draft_id": draft_id,
                       "call_id": call.call_id,
                       "draft_type": draft_request.draft_type,
                       "generated_by": generated_by,
                       "tenant_id": tenant_id
                   })
        
        # Record metrics
        metrics.followup_drafts_generated_total.labels(
            tenant_id=tenant_id,
            draft_type=draft_request.draft_type,
            generated_by=generated_by
        ).inc()
        
        # Return response
        return APIResponse(
            data=DraftResponse(
                draft_id=draft_id,
                call_id=call.call_id,
                draft_text=draft_text,
                draft_type=draft_request.draft_type,
                tone=draft_request.tone,
                status=DraftStatus.PENDING.value,
                blocked_by_quiet_hours=quiet_hours_check['is_blocked'],
                scheduled_send_time=scheduled_send_time.isoformat() if scheduled_send_time else None,
                generated_by=generated_by
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate follow-up draft: {str(e)}",
                    extra={"call_id": call.call_id, "tenant_id": tenant_id})
        
        raise HTTPException(
            status_code=500,
            detail=create_error_response(
                error_code=ErrorCodes.INTERNAL_ERROR,
                message="Failed to generate follow-up draft. Please try again.",
                request_id=request.state.trace_id
            ).dict()
        )


@router.get("/drafts", response_model=PaginatedResponse[Dict])
@require_role("admin", "rep")
async def list_followup_drafts(
    request: Request,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db)
):
    """
    List follow-up drafts.
    
    Reps see only their own drafts.
    Managers/execs see all drafts for their team.
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    user_role = request.state.user_role
    
    # Base query
    query = db.query(FollowUpDraft).filter_by(tenant_id=tenant_id)
    
    # Reps see only their drafts
    if user_role == "rep":
        query = query.filter_by(generated_for=user_id)
    
    # Filter by status
    if status:
        try:
            status_enum = DraftStatus(status)
            query = query.filter_by(status=status_enum)
        except ValueError:
            pass  # Invalid status, ignore
    
    # Get total
    total = query.count()
    
    # Paginate
    drafts = query.order_by(FollowUpDraft.created_at.desc())\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
    
    # Convert to dicts
    items = [d.to_dict() for d in drafts]
    
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


@router.post("/drafts/{draft_id}/approve")
@require_role("admin", "rep")
async def approve_draft(
    request: Request,
    draft_id: str,
    modified_text: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Approve follow-up draft (human-in-loop).
    Optionally modify before approving.
    """
    tenant_id = request.state.tenant_id
    user_id = request.state.user_id
    
    # Find draft
    draft = db.query(FollowUpDraft).filter_by(
        id=draft_id,
        tenant_id=tenant_id
    ).first()
    
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Update status
    draft.status = DraftStatus.APPROVED
    draft.approved_at = datetime.utcnow()
    draft.approved_by = user_id
    
    # If modified
    if modified_text:
        draft.modified_before_send = True
        draft.final_text = modified_text
    
    db.commit()
    
    logger.info(f"Draft approved",
               extra={"draft_id": draft_id, "modified": bool(modified_text)})
    
    return APIResponse(data={"status": "approved", "draft_id": draft_id})


@router.post("/drafts/{draft_id}/send")
@require_role("admin", "rep")
async def send_draft(
    request: Request,
    draft_id: str,
    db: Session = Depends(get_db)
):
    """
    Mark draft as sent (actual sending happens via Twilio/email service).
    Updates draft status and tracks usage.
    """
    tenant_id = request.state.tenant_id
    
    draft = db.query(FollowUpDraft).filter_by(
        id=draft_id,
        tenant_id=tenant_id
    ).first()
    
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Update status
    draft.status = DraftStatus.SENT
    draft.used = True
    draft.sent_at = datetime.utcnow()
    db.commit()
    
    return APIResponse(data={"status": "sent", "draft_id": draft_id})


# Helper Functions

def check_quiet_hours(phone_number: str, tenant_id: str, db: Session) -> Dict[str, Any]:
    """
    Check if sending is blocked by quiet hours (9PM-8AM local time).
    
    Returns:
        is_blocked: bool
        reason: str
        next_available_time: datetime or None
        local_time: datetime
    """
    # Get company timezone (default to US/Eastern)
    company = db.query(Company).filter_by(id=tenant_id).first()
    timezone_str = getattr(company, 'timezone', 'US/Eastern')
    
    try:
        tz = pytz.timezone(timezone_str)
    except:
        tz = pytz.timezone('US/Eastern')  # Fallback
    
    # Get current local time
    now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)
    now_local = now_utc.astimezone(tz)
    
    hour = now_local.hour
    
    # Quiet hours: 9PM (21:00) to 8AM (08:00)
    is_blocked = hour >= 21 or hour < 8
    
    if is_blocked:
        # Calculate next available time (8AM local)
        if hour >= 21:
            # After 9PM → wait until tomorrow 8AM
            next_available = now_local.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            # Before 8AM → wait until today 8AM
            next_available = now_local.replace(hour=8, minute=0, second=0, microsecond=0)
        
        return {
            "is_blocked": True,
            "reason": "quiet_hours",
            "next_available_time": next_available.astimezone(pytz.UTC).replace(tzinfo=None),
            "local_time": now_local
        }
    
    return {
        "is_blocked": False,
        "reason": None,
        "next_available_time": None,
        "local_time": now_local
    }


def generate_mock_draft(call: Call, draft_type: str, tone: str) -> str:
    """
    Generate mock follow-up draft for development.
    Returns realistic message based on call context.
    """
    customer_name = call.name or "there"
    
    if draft_type == "sms":
        if tone == "friendly":
            return f"Hi {customer_name}! Just wanted to follow up on our conversation. Did you have a chance to think about what we discussed? I'm here to answer any questions. - Otto AI Team"
        elif tone == "professional":
            return f"Hello {customer_name}, this is a follow-up regarding your recent inquiry. Please let me know if you need any additional information to move forward. Best regards."
        elif tone == "urgent":
            return f"{customer_name}, wanted to reach out quickly - we have limited availability this week and I wanted to make sure we could secure your preferred time. Can you confirm?"
        else:
            return f"Hi {customer_name}, following up on our call. Let me know if you have questions!"
    
    elif draft_type == "email":
        return f"""Subject: Following Up - Your Roofing Project

Hi {customer_name},

I wanted to follow up on our recent conversation about your roofing needs. 

Based on our discussion, I believe we can help you with [your specific need]. I'd love to answer any questions you might have.

Would you like to schedule a time to discuss next steps?

Best regards,
[Your Name]
[Company Name]

---
This message was assisted by Otto AI"""
    
    elif draft_type == "call_script":
        return f"""Call Script for {customer_name}:

1. GREETING:
   "Hi {customer_name}, this is [Your Name] from [Company]. Do you have a quick minute?"

2. REFERENCE PREVIOUS CONVERSATION:
   "I wanted to follow up on our conversation about [your roofing project]. Have you had a chance to think about it?"

3. ADDRESS OBJECTIONS:
   [Based on last call, they mentioned: price concerns]
   "I understand budget is important. I wanted to mention we have financing options that could make this more affordable."

4. NEXT STEPS:
   "Would you like me to send you more information, or would you prefer to schedule a time to discuss further?"

5. CLOSE:
   "Great, I'll [action item]. Thanks for your time!"

---
Generated by Otto AI"""
    
    return f"Mock {draft_type} draft for {customer_name}"


