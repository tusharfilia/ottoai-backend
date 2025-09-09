from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models import call, sales_rep, company, user, sales_manager
from app.routes.dependencies import get_user_from_clerk_token
import logging
import traceback

router = APIRouter(prefix="/appointments")
logger = logging.getLogger(__name__)

@router.get("")
async def get_appointments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_user_from_clerk_token),
    show_past: bool = False
):
    """
    Get all appointments (booked calls) for the authenticated sales rep (the ones the rep is assigned to).
    
    This endpoint retrieves all appointments that are:
    1. Assigned to the currently authenticated sales rep
    2. Not cancelled
    3. Can be filtered to show either upcoming or past appointments based on show_past parameter
    
    Args:
        show_past (bool): If True, shows past appointments. If False, shows upcoming appointments.
    """
    try:
        # Log the current user info for debugging
        logger.info(f"Processing appointment request for user: {current_user}")
        
        # Get user ID from the authenticated user
        user_id = current_user.get("id")
        if not user_id:
            logger.warning("User ID missing from authentication token")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        try:
            # Check if the user is a sales rep - wrap in try-except to catch DB errors
            sales_rep_record = db.query(sales_rep.SalesRep).filter_by(user_id=user_id).first()
        except Exception as db_error:
            logger.error(f"Database error querying sales rep: {str(db_error)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Database connection error")
            
        if not sales_rep_record:
            logger.warning(f"User {user_id} is not a sales representative")
            raise HTTPException(status_code=403, detail="User is not a sales representative")
        
        # Get the rep's company ID
        company_id = sales_rep_record.company_id
        logger.info(f"Found sales rep with company ID: {company_id}")
        
        try:
            # Base query conditions
            base_conditions = [
                call.Call.assigned_rep_id == user_id,
                call.Call.company_id == company_id,
                call.Call.booked.is_(True),
                call.Call.cancelled.is_(False)
            ]
            
            # Add date condition based on show_past parameter
            if show_past:
                base_conditions.append(call.Call.quote_date < datetime.now())
            else:
                base_conditions.append(call.Call.quote_date >= datetime.now())
            
            # Get all appointments (booked calls) assigned to this sales rep
            appointments = db.query(call.Call).filter(
                and_(*base_conditions)
            ).order_by(
                call.Call.quote_date.desc() if show_past else call.Call.quote_date.asc()
            ).all()
            
            logger.info(f"Retrieved {len(appointments)} {'past' if show_past else 'upcoming'} appointments for user {user_id}")
        except Exception as db_error:
            logger.error(f"Database error querying appointments: {str(db_error)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Database error retrieving appointments")
        
        # Format appointments for response
        appointment_list = []
        for appt in appointments:
            appointment_list.append({
                "id": appt.call_id,
                "title": f"Appointment with {appt.name}",
                "description": appt.address or "No address provided",
                "date": appt.quote_date.strftime("%Y-%m-%d") if appt.quote_date else None,
                "time": appt.quote_date.strftime("%H:%M:%S") if appt.quote_date else None,
                "full_datetime": appt.quote_date.isoformat() if appt.quote_date else None,
                "status": "cancelled" if appt.cancelled else "upcoming",
                "customer_name": appt.name,
                "customer_phone": appt.phone_number,
                "location": appt.address,
                "created_at": appt.created_at.isoformat() if appt.created_at else None,
                "duration": 60,  # Default duration in minutes
                "is_past": appt.quote_date < datetime.now() if appt.quote_date else False,
                "geofence": appt.geofence  # Include geofence data
            })
        
        return {
            "appointments": appointment_list,
            "total": len(appointment_list),
            "show_past": show_past
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions so they're handled properly
        raise
    except Exception as e:
        # Log the full stack trace for debugging
        stack_trace = traceback.format_exc()
        logger.error(f"Error retrieving appointments: {str(e)}\n{stack_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve appointments: {str(e)}")


@router.get("/company")
async def get_company_appointments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_user_from_clerk_token)
):
    """
    Get all appointments for the company - accessible only to sales managers.
    
    This endpoint retrieves all appointments in the manager's company that:
    1. Are not cancelled
    2. Includes both past and upcoming appointments
    
    This endpoint requires the user to have manager privileges.
    """
    try:
        # Get user ID from the authenticated user
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        # Check if the user is a sales manager
        manager_record = db.query(sales_manager.SalesManager).filter_by(user_id=user_id).first()
        if not manager_record:
            raise HTTPException(status_code=403, detail="User is not a sales manager")
        
        # Get the manager's company ID
        company_id = manager_record.company_id
        
        # Get all appointments in the company
        appointments = db.query(call.Call).filter(
            and_(
                call.Call.company_id == company_id,
                call.Call.booked.is_(True),
                call.Call.cancelled.is_(False),
            )
        ).order_by(call.Call.quote_date.asc()).all()
        
        # Format appointments for response
        appointment_list = []
        for appt in appointments:
            # Get sales rep name if assigned
            rep_name = "Unassigned"
            if appt.assigned_rep_id:
                user_record = db.query(user.User).filter_by(id=appt.assigned_rep_id).first()
                if user_record:
                    rep_name = user_record.name
            
            appointment_list.append({
                "id": appt.call_id,
                "title": f"Appointment with {appt.name}",
                "description": appt.address or "No address provided",
                "date": appt.quote_date.strftime("%Y-%m-%d") if appt.quote_date else None,
                "time": appt.quote_date.strftime("%H:%M:%S") if appt.quote_date else None,
                "full_datetime": appt.quote_date.isoformat() if appt.quote_date else None,
                "status": "cancelled" if appt.cancelled else "upcoming",
                "customer_name": appt.name,
                "customer_phone": appt.phone_number,
                "location": appt.address,
                "created_at": appt.created_at.isoformat() if appt.created_at else None,
                "duration": 60,  # Default duration in minutes
                "assigned_to": rep_name,
                "is_assigned_to_me": appt.assigned_rep_id == user_id,
                "geofence": appt.geofence  # Include geofence data
            })
        
        return {
            "appointments": appointment_list,
            "total": len(appointment_list),
            "company_name": manager_record.company.name if manager_record.company else "Unknown Company"
        }
    
    except Exception as e:
        logger.error(f"Error retrieving company appointments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve company appointments: {str(e)}")


@router.get("/{appointment_id}")
async def get_appointment_details(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_user_from_clerk_token)
):
    """
    Get detailed information about a specific appointment.
    """
    try:
        # Get user ID from the authenticated user
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        # Check if the user is a sales rep
        sales_rep_record = db.query(sales_rep.SalesRep).filter_by(user_id=user_id).first()
        if not sales_rep_record:
            raise HTTPException(status_code=403, detail="User is not a sales representative")
        
        # Get the rep's company ID
        company_id = sales_rep_record.company_id
        
        # Get the specific appointment
        appointment = db.query(call.Call).filter(
            and_(
                call.Call.call_id == appointment_id,
                call.Call.company_id == company_id,
                call.Call.booked.is_(True)
            )
        ).first()
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        # Check if the appointment is assigned to this rep or within their company
        if appointment.assigned_rep_id != user_id and appointment.company_id != company_id:
            raise HTTPException(status_code=403, detail="You don't have permission to view this appointment")
        
        # Get sales rep name if assigned
        rep_name = "Unassigned"
        if appointment.assigned_rep_id:
            user_record = db.query(user.User).filter_by(id=appointment.assigned_rep_id).first()
            if user_record:
                rep_name = user_record.name
        
        # Format appointment for response with more details
        appointment_details = {
            "id": appointment.call_id,
            "title": f"Appointment with {appointment.name}",
            "description": appointment.address or "No address provided",
            "date": appointment.quote_date.strftime("%Y-%m-%d") if appointment.quote_date else None,
            "time": appointment.quote_date.strftime("%H:%M:%S") if appointment.quote_date else None,
            "full_datetime": appointment.quote_date.isoformat() if appointment.quote_date else None,
            "status": "cancelled" if appointment.cancelled else "upcoming",
            "customer_name": appointment.name,
            "customer_phone": appointment.phone_number,
            "location": appointment.address,
            "created_at": appointment.created_at.isoformat() if appointment.created_at else None,
            "duration": 60,  # Default duration in minutes
            "assigned_to": rep_name,
            "is_assigned_to_me": appointment.assigned_rep_id == user_id,
            "transcript": appointment.transcript,
            "bought": appointment.bought,
            "rescheduled": appointment.rescheduled,
            "cancelled": appointment.cancelled,
            "reason_for_cancellation": appointment.reason_for_cancellation,
            "price_quote": float(appointment.price_if_bought) if appointment.price_if_bought else None,
            "geofence": appointment.geofence  # Include geofence data
        }
        
        return appointment_details
    
    except Exception as e:
        logger.error(f"Error retrieving appointment details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve appointment details: {str(e)}") 