"""
Pydantic schemas for onboarding endpoints.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum


class CallProviderEnum(str, Enum):
    """Call provider enum."""
    CALLRAIL = "callrail"
    TWILIO = "twilio"


class DocumentCategoryEnum(str, Enum):
    """Document category enum."""
    SOP = "sop"
    TRAINING = "training"
    REFERENCE = "reference"
    POLICY = "policy"


class IngestionStatusEnum(str, Enum):
    """Ingestion status enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


# Phase 1: Company Basics
class CompanyBasicsRequest(BaseModel):
    """Request schema for company basics step."""
    company_name: str = Field(..., description="Company name")
    company_phone: str = Field(..., description="Company phone number")
    company_email: EmailStr = Field(..., description="Company email address")
    company_domain: str = Field(..., description="Company domain (e.g., example.com)")
    company_address: Optional[str] = Field(None, description="Company address")
    industry: str = Field(..., description="Industry type")
    timezone: str = Field(default="America/New_York", description="Timezone (IANA format)")
    team_size: int = Field(..., ge=1, description="Number of team members")
    admin_name: str = Field(..., description="Admin/manager name")
    admin_email: EmailStr = Field(..., description="Admin/manager email")
    
    @validator('company_domain')
    def validate_domain(cls, v):
        """Validate domain format."""
        if not v or '.' not in v:
            raise ValueError('Invalid domain format')
        return v.lower().strip()


class CompanyBasicsResponse(BaseModel):
    """Response schema for company basics step."""
    success: bool
    company_id: str
    onboarding_step: str
    step_already_completed: bool = False


# Phase 2: Call Tracking Integration
class CallRailConnectRequest(BaseModel):
    """Request schema for CallRail connection."""
    api_key: str = Field(..., description="CallRail API key")
    account_id: str = Field(..., description="CallRail account ID")
    primary_tracking_number: Optional[str] = Field(None, description="Primary tracking phone number")


class TwilioConnectRequest(BaseModel):
    """Request schema for Twilio connection."""
    account_sid: str = Field(..., description="Twilio Account SID")
    auth_token: str = Field(..., description="Twilio Auth Token")
    primary_tracking_number: str = Field(..., description="Primary tracking phone number")


class CallTrackingTestResponse(BaseModel):
    """Response schema for call tracking test."""
    success: bool
    connected: bool
    webhook_url: str
    message: str


class CallTrackingConnectResponse(BaseModel):
    """Response schema for call tracking connection."""
    success: bool
    provider: str
    onboarding_step: str
    webhook_url: str
    step_already_completed: bool = False


# Phase 3: Document Upload
class DocumentUploadRequest(BaseModel):
    """Request schema for document upload (metadata only - file comes as multipart)."""
    category: DocumentCategoryEnum = Field(..., description="Document category")
    role_target: Optional[str] = Field(None, description="Target role (manager, csr, sales_rep) or None for all")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional document metadata")


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""
    success: bool
    document_id: str
    filename: str
    s3_url: str
    ingestion_job_id: Optional[str] = None
    ingestion_status: str
    estimated_processing_time: Optional[str] = None


class DocumentStatusResponse(BaseModel):
    """Response schema for document status check."""
    document_id: str
    ingestion_status: str
    ingestion_job_id: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


# Phase 4: Goals & Preferences
class GoalsPreferencesRequest(BaseModel):
    """Request schema for goals and preferences step."""
    primary_goals: List[str] = Field(..., description="List of primary goals/KPIs")
    target_metrics: Optional[Dict[str, Any]] = Field(None, description="Target metrics (e.g., conversion_rate, response_time)")
    notification_preferences: Optional[Dict[str, Any]] = Field(None, description="Notification preferences")
    quiet_hours_start: Optional[str] = Field(None, description="Quiet hours start time (HH:MM format)")
    quiet_hours_end: Optional[str] = Field(None, description="Quiet hours end time (HH:MM format)")


class GoalsPreferencesResponse(BaseModel):
    """Response schema for goals and preferences step."""
    success: bool
    onboarding_step: str
    step_already_completed: bool = False


# Phase 5: Team Invitations
class InviteUserRequest(BaseModel):
    """Request schema for inviting a user."""
    email: EmailStr = Field(..., description="User email address")
    role: str = Field(..., description="User role (manager, csr, sales_rep)")
    territory: Optional[str] = Field(None, description="Territory (for sales reps)")
    department: Optional[str] = Field(None, description="Department/team name")
    
    @validator('role')
    def validate_role(cls, v):
        """Validate role."""
        valid_roles = ['manager', 'csr', 'sales_rep']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v


class InviteUserResponse(BaseModel):
    """Response schema for inviting a user."""
    success: bool
    invite_id: str
    email: str
    role: str
    status: str  # "sent", "pending", "accepted"


class InvitedUserResponse(BaseModel):
    """Response schema for listing invited users."""
    invite_id: str
    email: str
    role: str
    territory: Optional[str] = None
    status: str
    invited_at: datetime
    accepted_at: Optional[datetime] = None


class InvitedUsersListResponse(BaseModel):
    """Response schema for listing all invited users."""
    invited_users: List[InvitedUserResponse]
    total: int


# Phase 6: Verification
class VerificationRequest(BaseModel):
    """Request schema for final verification."""
    pass  # No fields needed, just triggers verification


class VerificationResponse(BaseModel):
    """Response schema for final verification."""
    success: bool
    onboarding_completed: bool
    onboarding_completed_at: Optional[datetime] = None
    checks: Dict[str, bool] = Field(..., description="Verification checks (company_basics, call_tracking, documents, team_members)")
    errors: List[str] = Field(default_factory=list, description="List of errors if verification failed")


# Status & Progress
class OnboardingStatusResponse(BaseModel):
    """Response schema for onboarding status check."""
    company_id: str
    onboarding_step: str
    onboarding_completed: bool
    onboarding_completed_at: Optional[datetime] = None
    progress: Dict[str, Any] = Field(..., description="Progress details for each step")






