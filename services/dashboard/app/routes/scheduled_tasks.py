from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from ..database import get_db
from ..models import call, sales_manager, scheduled_call
from ..services.twilio_service import twilio_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled", tags=["scheduled"])

@router.post("/process-unassigned-calls")
async def process_unassigned_calls(db: Session = Depends(get_db)):
    # Add date filtering to only process today's calls
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    unassigned_calls = db.query(call.Call).filter(
        call.Call.assigned_rep_id.is_(None),
        call.Call.booked == True,
        call.Call.created_at.between(today_start, today_end)  # Add date filter
    ).all()
    
    if not unassigned_calls:
        return {"message": "No unassigned calls to process"}
    
    # Group calls by company
    company_calls = {}
    for call_record in unassigned_calls:
        if call_record.company_id not in company_calls:
            company_calls[call_record.company_id] = []
        company_calls[call_record.company_id].append(call_record)
    
    # Notify sales managers for each company
    for company_id, calls in company_calls.items():
        # Get company's sales managers
        managers = db.query(sales_manager.SalesManager).filter(
            sales_manager.SalesManager.company_id == company_id
        ).all()
        
        # Send notification to managers
        await notify_managers(managers, len(calls))
    
    return {"message": f"Processed {len(unassigned_calls)} unassigned calls"}

async def notify_managers(managers: List[sales_manager.SalesManager], call_count: int):
    """
    Send notifications to managers about unassigned calls.
    
    Args:
        managers: List of sales manager objects
        call_count: Number of unassigned calls
    """
    if not managers:
        logger.warning("No managers to notify about unassigned calls")
        return
    
    logger.info(f"Notifying {len(managers)} managers about {call_count} unassigned calls")
    
    success_count = 0
    for manager in managers:
        try:
            result = twilio_service.notify_sales_manager(
                manager_phone=manager.phone_number,
                unassigned_calls_count=call_count
            )
            
            if result["status"] == "success":
                success_count += 1
                logger.info(f"Successfully notified manager {manager.name} (ID: {manager.id})")
            else:
                logger.error(f"Failed to notify manager {manager.name} (ID: {manager.id}): {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error notifying manager {manager.name} (ID: {manager.id}): {str(e)}")
    
    logger.info(f"Notification summary: {success_count}/{len(managers)} successful")
    return {
        "total_managers": len(managers),
        "success_count": success_count
    } 