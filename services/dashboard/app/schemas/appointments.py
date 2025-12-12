from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class AppointmentListItem(BaseModel):
    """Schema for a single appointment in a list view."""
    
    appointment_id: str = Field(..., description="Unique appointment identifier")
    lead_id: Optional[str] = Field(None, description="Associated lead ID")
    contact_card_id: Optional[str] = Field(None, description="Associated contact card ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    address: Optional[str] = Field(None, description="Appointment location/address")
    scheduled_start: datetime = Field(..., description="Scheduled start time")
    scheduled_end: Optional[datetime] = Field(None, description="Scheduled end time")
    status: str = Field(..., description="Appointment status")
    outcome: str = Field(..., description="Appointment outcome")
    service_type: Optional[str] = Field(None, description="Type of service")
    is_assigned_to_me: bool = Field(False, description="Whether appointment is assigned to requesting user")
    deal_size: Optional[float] = Field(None, description="Deal size value")
    pending_tasks_count: int = Field(0, description="Number of pending tasks")
    
    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    """Response schema for appointment list endpoints."""
    
    appointments: List[AppointmentListItem] = Field(..., description="List of appointments")
    total: int = Field(..., description="Total number of appointments")
    date: str = Field(..., description="Filter date in ISO format")
    
    class Config:
        from_attributes = True


