"""
API endpoints for Missed Call Queue System
Provides management and monitoring of missed call recovery
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

from app.database import get_db
from app.middleware.rbac import require_role
from app.services.missed_call_queue_service import MissedCallQueueService
from app.services.queue_processor import queue_processor
from app.models.missed_call_queue import MissedCallQueue, MissedCallStatus, MissedCallPriority
from app.schemas.responses import APIResponse, PaginatedResponse, PaginationMeta
from app.obs.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/missed-calls", tags=["missed-calls", "queue"])

# Initialize service
missed_call_service = MissedCallQueueService()

@router.post("/queue/{call_id}")
@require_role("manager", "csr")
async def add_missed_call_to_queue(
    request: Request,
    call_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Add a missed call to the recovery queue
    
    This endpoint is called when a call is missed and needs to be processed
    through the AI-led recovery system.
    """
    try:
        # Get call record
        from app.models.call import Call
        call_record = db.query(Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Add to queue
        queue_entry = await missed_call_service.add_missed_call_to_queue(
            call_id=call_id,
            customer_phone=call_record.phone_number,
            company_id=call_record.company_id,
            db=db
        )
        
        # Trigger immediate processing
        background_tasks.add_task(
            queue_processor.process_single_queue_entry,
            queue_entry.id
        )
        
        return APIResponse(data={
            "queue_id": queue_entry.id,
            "status": queue_entry.status.value,
            "priority": queue_entry.priority.value,
            "sla_deadline": queue_entry.sla_deadline.isoformat(),
            "escalation_deadline": queue_entry.escalation_deadline.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error adding missed call to queue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queue/status")
@require_role("manager", "csr")
async def get_queue_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get current queue status for the company"""
    try:
        company_id = request.state.tenant_id
        status_counts = await missed_call_service.get_queue_status(company_id, db)
        
        return APIResponse(data={
            "company_id": company_id,
            "status_counts": status_counts,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queue/metrics")
@require_role("manager", "csr")
async def get_queue_metrics(
    request: Request,
    company_id: Optional[str] = Query(None, description="Company ID (optional, defaults to tenant_id from JWT)"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """Get queue performance metrics"""
    try:
        tenant_id = request.state.tenant_id
        
        # Use company_id from query if provided, otherwise use tenant_id from JWT
        # Validate that company_id matches tenant_id if provided
        if company_id and company_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: company_id does not match your organization"
            )
        
        target_company_id = company_id or tenant_id
        
        # Parse dates to handle YYYY-MM-DD format properly
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            try:
                # Handle YYYY-MM-DD format
                if 'T' in start_date:
                    parsed_start_date = start_date
                else:
                    # Convert YYYY-MM-DD to ISO format
                    parsed_start_date = datetime.strptime(start_date, '%Y-%m-%d').isoformat()
            except ValueError as e:
                logger.warning(f"Invalid start_date format: {start_date}, error: {str(e)}")
        
        if end_date:
            try:
                # Handle YYYY-MM-DD format
                if 'T' in end_date:
                    parsed_end_date = end_date
                else:
                    # Convert YYYY-MM-DD to ISO format (end of day)
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                    parsed_end_date = end_dt.isoformat()
            except ValueError as e:
                logger.warning(f"Invalid end_date format: {end_date}, error: {str(e)}")
        
        metrics = await missed_call_service.get_queue_metrics(
            target_company_id, 
            db, 
            start_date=parsed_start_date, 
            end_date=parsed_end_date
        )
        
        return APIResponse(data={
            "company_id": target_company_id,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queue/entries")
@require_role("manager", "csr")
async def get_queue_entries(
    request: Request,
    company_id: Optional[str] = Query(None, description="Company ID (optional, defaults to tenant_id from JWT)"),
    page: int = 1,
    page_size: int = 50,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get paginated list of queue entries"""
    try:
        tenant_id = request.state.tenant_id
        
        # Use company_id from query if provided, otherwise use tenant_id from JWT
        # Validate that company_id matches tenant_id if provided
        if company_id and company_id != tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: company_id does not match your organization"
            )
        
        target_company_id = company_id or tenant_id
        
        # Build query
        query = db.query(MissedCallQueue).filter_by(company_id=target_company_id)
        
        # Apply filters
        if status:
            try:
                status_enum = MissedCallStatus(status)
                query = query.filter_by(status=status_enum)
            except ValueError:
                pass  # Invalid status, ignore filter
        
        if priority:
            try:
                priority_enum = MissedCallPriority(priority)
                query = query.filter_by(priority=priority_enum)
            except ValueError:
                pass  # Invalid priority, ignore filter
        
        # Get total count
        total = query.count()
        
        # Paginate
        entries = query.order_by(
            MissedCallQueue.priority.desc(),
            MissedCallQueue.created_at.asc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        
        # Convert to dicts
        items = []
        for entry in entries:
            items.append({
                "id": entry.id,
                "call_id": entry.call_id,
                "customer_phone": entry.customer_phone,
                "status": entry.status.value,
                "priority": entry.priority.value,
                "customer_type": entry.customer_type,
                "retry_count": entry.retry_count,
                "sla_deadline": entry.sla_deadline.isoformat(),
                "escalation_deadline": entry.escalation_deadline.isoformat(),
                "created_at": entry.created_at.isoformat(),
                "updated_at": entry.updated_at.isoformat()
            })
        
        # Build pagination metadata
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue entries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queue/entries/{queue_id}")
@require_role("manager", "csr")
async def get_queue_entry(
    request: Request,
    queue_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific queue entry"""
    try:
        company_id = request.state.tenant_id
        
        entry = db.query(MissedCallQueue).filter_by(
            id=queue_id,
            company_id=company_id
        ).first()
        
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        
        # Get attempts
        attempts = []
        for attempt in entry.attempts:
            attempts.append({
                "id": attempt.id,
                "attempt_number": attempt.attempt_number,
                "method": attempt.method,
                "message_sent": attempt.message_sent,
                "response_received": attempt.response_received,
                "success": attempt.success,
                "customer_engaged": attempt.customer_engaged,
                "attempted_at": attempt.attempted_at.isoformat(),
                "responded_at": attempt.responded_at.isoformat() if attempt.responded_at else None
            })
        
        return APIResponse(data={
            "id": entry.id,
            "call_id": entry.call_id,
            "customer_phone": entry.customer_phone,
            "status": entry.status.value,
            "priority": entry.priority.value,
            "customer_type": entry.customer_type,
            "retry_count": entry.retry_count,
            "max_retries": entry.max_retries,
            "sla_deadline": entry.sla_deadline.isoformat(),
            "escalation_deadline": entry.escalation_deadline.isoformat(),
            "ai_rescue_attempted": entry.ai_rescue_attempted,
            "customer_responded": entry.customer_responded,
            "conversation_context": json.loads(entry.conversation_context) if entry.conversation_context else {},
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
            "processed_at": entry.processed_at.isoformat() if entry.processed_at else None,
            "escalated_at": entry.escalated_at.isoformat() if entry.escalated_at else None,
            "attempts": attempts
        })
        
    except Exception as e:
        logger.error(f"Error getting queue entry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queue/entries/{queue_id}/process")
@require_role("manager", "csr")
async def process_queue_entry(
    request: Request,
    queue_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger processing of a specific queue entry"""
    try:
        company_id = request.state.tenant_id
        
        # Verify queue entry exists and belongs to company
        entry = db.query(MissedCallQueue).filter_by(
            id=queue_id,
            company_id=company_id
        ).first()
        
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        
        # Trigger processing
        background_tasks.add_task(
            queue_processor.process_single_queue_entry,
            queue_id
        )
        
        return APIResponse(data={
            "queue_id": queue_id,
            "status": "processing_triggered",
            "message": "Queue entry processing has been triggered"
        })
        
    except Exception as e:
        logger.error(f"Error processing queue entry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queue/entries/{queue_id}/escalate")
@require_role("manager", "csr")
async def escalate_queue_entry(
    request: Request,
    queue_id: int,
    reason: str = "manual_escalation",
    db: Session = Depends(get_db)
):
    """Manually escalate a queue entry to human CSR"""
    try:
        company_id = request.state.tenant_id
        
        # Get queue entry
        entry = db.query(MissedCallQueue).filter_by(
            id=queue_id,
            company_id=company_id
        ).first()
        
        if not entry:
            raise HTTPException(status_code=404, detail="Queue entry not found")
        
        # Update status
        entry.status = MissedCallStatus.ESCALATED
        entry.escalated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Queue entry {queue_id} escalated manually: {reason}")
        
        return APIResponse(data={
            "queue_id": queue_id,
            "status": "escalated",
            "reason": reason,
            "escalated_at": entry.escalated_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error escalating queue entry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/processor/status")
@require_role("manager")
async def get_processor_status():
    """Get background processor status and statistics"""
    try:
        status = await queue_processor.get_processor_status()
        return APIResponse(data=status)
        
    except Exception as e:
        logger.error(f"Error getting processor status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/processor/start")
@require_role("manager")
async def start_processor():
    """Start the background queue processor"""
    try:
        await queue_processor.start()
        return APIResponse(data={
            "status": "started",
            "message": "Queue processor started successfully"
        })
        
    except Exception as e:
        logger.error(f"Error starting processor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/processor/stop")
@require_role("manager")
async def stop_processor():
    """Stop the background queue processor"""
    try:
        await queue_processor.stop()
        return APIResponse(data={
            "status": "stopped",
            "message": "Queue processor stopped successfully"
        })
        
    except Exception as e:
        logger.error(f"Error stopping processor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

















@router.post("/queue/{call_id}")
@require_role("manager", "csr")
async def add_missed_call_to_queue(
    request: Request,
    call_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Add a missed call to the recovery queue
    
    This endpoint is called when a call is missed and needs to be processed
    through the AI-led recovery system.
    """
    try:
        # Get call record
        from app.models.call import Call
        call_record = db.query(Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Add to queue
        queue_entry = await missed_call_service.add_missed_call_to_queue(
            call_id=call_id,
            customer_phone=call_record.phone_number,
            company_id=call_record.company_id,
            db=db
        )
        
        # Trigger immediate processing
        background_tasks.add_task(
            queue_processor.process_single_queue_entry,
            queue_entry.id
        )
        
        return APIResponse(data={
            "queue_id": queue_entry.id,
            "status": queue_entry.status.value,
            "priority": queue_entry.priority.value,
            "sla_deadline": queue_entry.sla_deadline.isoformat(),
            "escalation_deadline": queue_entry.escalation_deadline.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error adding missed call to queue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

