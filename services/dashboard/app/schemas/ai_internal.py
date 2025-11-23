"""
Pydantic schemas for internal AI API endpoints.

These schemas are used by Shunya/UWC to fetch metadata for Ask Otto AI.
Keep schemas minimal, stable, and JSON-friendly.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class AICallResponse(BaseModel):
    """Call metadata for internal AI API."""
    call_id: int
    company_id: str
    lead_id: Optional[str] = None
    contact_card_id: Optional[str] = None
    rep_id: Optional[str] = None
    phone_number: Optional[str] = None
    is_missed: bool = False
    direction: Optional[str] = None  # inbound, outbound
    source: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    booking_outcome: Optional[str] = None  # booked, unbooked, service_not_offered, pending
    appointment_id: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AIRepResponse(BaseModel):
    """Sales rep metadata for internal AI API."""
    rep_id: str
    company_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    region: Optional[str] = None
    active: bool = True
    
    class Config:
        from_attributes = True


class AICompanyResponse(BaseModel):
    """Company metadata for internal AI API."""
    company_id: str
    name: str
    timezone: Optional[str] = None
    service_areas: Optional[List[str]] = None
    services_offered: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AIContactSummary(BaseModel):
    """Contact summary for internal AI API."""
    name: Optional[str] = None  # first + last name
    phones: List[str] = []
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    
    class Config:
        from_attributes = True


class AIAppointmentSummary(BaseModel):
    """Appointment summary for internal AI API."""
    id: str
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    status: str
    outcome: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AILeadResponse(BaseModel):
    """Lead metadata for internal AI API (compound response)."""
    lead: dict
    contact: AIContactSummary
    appointments: List[AIAppointmentSummary] = []
    
    class Config:
        from_attributes = True


class AIAppointmentResponse(BaseModel):
    """Appointment metadata for internal AI API (compound response)."""
    appointment: dict
    lead: dict
    contact: AIContactSummary
    
    class Config:
        from_attributes = True


class AIServiceCatalogResponse(BaseModel):
    """Service catalog for internal AI API."""
    company_id: str
    services: List[dict] = []
    
    class Config:
        from_attributes = True


