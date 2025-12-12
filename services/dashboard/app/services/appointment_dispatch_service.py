"""
Appointment Dispatch Service for CSR-led manual dispatching to Sales Reps.

Handles:
- Assignment of appointments to sales reps
- Double-booking conflict detection
- Shunya booking semantics enforcement
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.appointment import Appointment, AppointmentStatus
from app.models.call_analysis import CallAnalysis
from app.models.enums import BookingStatus
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class AppointmentDispatchError(Exception):
    """Raised when appointment dispatch fails."""
    pass


class AppointmentDispatchService:
    """Service for dispatching appointments to sales reps."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def assign_appointment_to_rep(
        self,
        *,
        tenant_id: str,
        appointment_id: str,
        rep_id: str,
        actor_id: str,
        allow_double_booking: bool = False
    ) -> Appointment:
        """
        Assign an appointment to a sales rep.
        
        Args:
            tenant_id: Company/tenant ID
            appointment_id: Appointment ID
            rep_id: Sales rep user ID to assign to
            actor_id: User ID of the CSR/manager performing the assignment
            allow_double_booking: If True, skip double-booking check
        
        Returns:
            Updated Appointment instance
        
        Raises:
            AppointmentDispatchError: If assignment fails (not booked, double-booking, etc.)
        """
        # Fetch appointment
        appointment = self.db.query(Appointment).filter(
            Appointment.id == appointment_id,
            Appointment.company_id == tenant_id
        ).first()
        
        if not appointment:
            raise AppointmentDispatchError(f"Appointment {appointment_id} not found")
        
        # Enforce Shunya booking semantics: appointment must be booked
        # Check if the originating call has booking_status == "booked"
        if appointment.lead_id:
            # Find the call analysis that created this appointment
            # We check the most recent call analysis for this lead
            from app.models.call import Call
            call = self.db.query(Call).filter(
                Call.lead_id == appointment.lead_id,
                Call.company_id == tenant_id
            ).order_by(Call.created_at.desc()).first()
            
            if call:
                call_analysis = self.db.query(CallAnalysis).filter(
                    CallAnalysis.call_id == call.call_id,
                    CallAnalysis.tenant_id == tenant_id
                ).first()
                
                if call_analysis:
                    # Check booking_status from Shunya
                    booking_status = call_analysis.booking_status
                    if booking_status != BookingStatus.BOOKED.value:
                        raise AppointmentDispatchError(
                            f"Appointment cannot be assigned: booking_status is '{booking_status}', expected 'booked'"
                        )
        
        # P0 FIX: Acquire distributed lock to prevent concurrent assignment requests
        from app.services.redis_lock_service import redis_lock_service
        import asyncio
        lock_key = f"appointment:assign:{appointment_id}"
        lock_token = None
        
        try:
            lock_token = asyncio.run(
                redis_lock_service.acquire_lock(
                    lock_key=lock_key,
                    tenant_id=tenant_id,
                    timeout=60  # 1 minute
                )
            )
            
            if not lock_token:
                raise AppointmentDispatchError(
                    f"Could not acquire lock for assigning appointment {appointment_id}"
                )
            
            # Refresh appointment from DB to get latest state (inside lock)
            self.db.refresh(appointment)
            
            # Double-booking check (unless allowed) - inside lock
            if not allow_double_booking:
                # Check for overlapping appointments for the same rep
                # Overlap: same rep, scheduled_start within appointment window
                appointment_start = appointment.scheduled_start
                appointment_end = appointment.scheduled_end or (appointment_start + timedelta(hours=1))  # Default 1 hour
                
                overlapping = self.db.query(Appointment).filter(
                    Appointment.company_id == tenant_id,
                    Appointment.assigned_rep_id == rep_id,
                    Appointment.id != appointment_id,  # Exclude current appointment
                    Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
                    # Overlap condition: other appointment starts before this one ends AND ends after this one starts
                    Appointment.scheduled_start < appointment_end,
                    or_(
                        Appointment.scheduled_end.is_(None),
                        Appointment.scheduled_end > appointment_start
                    )
                ).first()
                
                if overlapping:
                    raise AppointmentDispatchError(
                        f"Double-booking conflict: Rep {rep_id} already has appointment {overlapping.id} "
                        f"scheduled at {overlapping.scheduled_start} (overlaps with {appointment_start})"
                    )
            
            # Update assignment fields
            appointment.assigned_rep_id = rep_id
            appointment.assigned_by_csr_id = actor_id
            appointment.assigned_by = actor_id  # Also update legacy field
            appointment.assigned_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(appointment)
        finally:
            # Always release lock
            if lock_token:
                asyncio.run(
                    redis_lock_service.release_lock(
                        lock_key=lock_key,
                        tenant_id=tenant_id,
                        lock_token=lock_token
                    )
                )
        
        logger.info(
            f"Assigned appointment {appointment_id} to rep {rep_id} by CSR {actor_id}",
            extra={
                "appointment_id": appointment_id,
                "rep_id": rep_id,
                "actor_id": actor_id,
                "tenant_id": tenant_id
            }
        )
        
        return appointment

