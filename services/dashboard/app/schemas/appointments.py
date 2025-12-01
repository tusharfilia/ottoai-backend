"""
Pydantic schemas for Appointment endpoints.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.appointment import AppointmentStatus, AppointmentOutcome


class AppointmentListItem(BaseModel):
    """Compact appointment item for listing endpoints (mobile-friendly)."""
    appointment_id: str = Field(..., description="Appointment identifier")
    lead_id: str = Field(..., description="Associated lead ID")
    contact_card_id: Optional[str] = Field(None, description="Associated contact card ID")
    customer_name: Optional[str] = Field(None, description="Customer name from contact card")
    address: Optional[str] = Field(None, description="Appointment location/address")
    scheduled_start: datetime = Field(..., description="Scheduled start time")
    scheduled_end: Optional[datetime] = Field(None, description="Scheduled end time")
    status: str = Field(..., description="Appointment status")
    outcome: str = Field(..., description="Appointment outcome")
    service_type: Optional[str] = Field(None, description="Service type")
    is_assigned_to_me: bool = Field(..., description="Whether appointment is assigned to requesting rep")
    deal_size: Optional[float] = Field(None, description="Deal size if outcome is won")
    pending_tasks_count: Optional[int] = Field(None, description="Number of pending tasks (if cheap to compute)")
    
    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    """Response for appointment listing."""
    appointments: List[AppointmentListItem] = Field(default_factory=list)
    total: int = Field(..., description="Total count matching filters")
    date: Optional[str] = Field(None, description="Date filter applied (ISO format)")


