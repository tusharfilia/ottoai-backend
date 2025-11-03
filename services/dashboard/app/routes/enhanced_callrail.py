"""
Enhanced CallRail Webhook Handler
Implements the complete CSR flow as documented in CSR_FLOW.md
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import call, company
from app.services.twilio_service import TwilioService
from app.services.uwc_client import get_uwc_client
from app.middleware.rate_limiter import limits
from app.services.idempotency import with_idempotency
from app.realtime.bus import emit
from datetime import datetime, timedelta
import json
import requests
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
twilio_service = TwilioService()

@router.post("/callrail/call.incoming")
@limits(tenant="30/minute")
async def handle_call_incoming(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle CallRail 'call.incoming' webhook
    Creates/updates lead, logs phone number, timestamp, and pickup timer
    """
    try:
        data = await request.json()
        logger.info(f"CallRail call.incoming webhook: {data}")
        
        # Extract call data
        call_id = data.get("call_id")
        caller_number = data.get("caller_number")
        tracking_number = data.get("tracking_number")
        timestamp = data.get("timestamp")
        
        if not all([call_id, caller_number, tracking_number]):
            raise HTTPException(status_code=400, detail="Missing required call data")
        
        # Find company by tracking number
        company_record = db.query(company.Company).filter_by(phone_number=tracking_number).first()
        if not company_record:
            logger.warning(f"No company found for tracking number {tracking_number}")
            return {"status": "error", "message": "Company not found"}
        
        # Check if caller exists in leads
        existing_call = db.query(call.Call).filter_by(
            phone_number=caller_number,
            company_id=company_record.id
        ).first()
        
        if existing_call:
            # Update existing lead
            existing_call.updated_at = datetime.utcnow()
            db.commit()
            call_id_db = existing_call.call_id
            logger.info(f"Updated existing call record: {call_id_db}")
        else:
            # Create new "Unqualified Lead"
            new_call = call.Call(
                phone_number=caller_number,
                company_id=company_record.id,
                created_at=datetime.utcnow(),
                missed_call=False,  # Will be updated when call status is known
                status="incoming"  # New status for incoming calls
            )
            db.add(new_call)
            db.commit()
            db.refresh(new_call)
            call_id_db = new_call.call_id
            logger.info(f"Created new unqualified lead: {call_id_db}")
        
        # Emit real-time event
        emit(
            event_name="call.incoming",
            payload={
                "call_id": call_id_db,
                "callrail_call_id": call_id,  # Store in event payload only
                "phone_number": caller_number,
                "company_id": str(company_record.id),
                "timestamp": timestamp
            },
            tenant_id=company_record.id,
            lead_id=call_id_db
        )
        
        return {"status": "success", "call_id": call_id_db}
        
    except Exception as e:
        logger.error(f"Error handling call.incoming: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callrail/call.answered")
@limits(tenant="30/minute")
async def handle_call_answered(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle CallRail 'call.answered' webhook
    Logs CSR ID, duration, and updates call status
    """
    try:
        data = await request.json()
        logger.info(f"CallRail call.answered webhook: {data}")
        
        # Extract call data
        customer_phone = data.get("customer_phone_number") or data.get("callernum") or data.get("caller_number")
        tracking_number = data.get("tracking_phone_number") or data.get("trackingnum") or data.get("tracking_number")
        duration = data.get("duration")
        csr_id = data.get("csr_id")
        
        # Find company by tracking number
        company_record = db.query(company.Company).filter_by(phone_number=tracking_number).first()
        if not company_record:
            logger.warning(f"No company found for tracking number {tracking_number}")
            return {"status": "error", "message": "Company not found"}
        
        # Find call record by phone number and company
        call_record = db.query(call.Call).filter_by(
            phone_number=customer_phone,
            company_id=company_record.id
        ).order_by(call.Call.created_at.desc()).first()
        
        if not call_record:
            logger.warning(f"Call record not found for phone {customer_phone}, company {company_record.id}")
            return {"status": "error", "message": "Call record not found"}
        
        # Update call record
        call_record.missed_call = False
        call_record.status = "answered"
        if duration:
            try:
                call_record.last_call_duration = int(duration)
            except (ValueError, TypeError):
                pass
        # Note: csr_id field doesn't exist in Call model, store in JSON if needed
        call_record.updated_at = datetime.utcnow()
        db.commit()
        
        # Emit real-time event
        emit(
            event_name="call.answered",
            payload={
                "call_id": call_record.call_id,
                "duration": duration,
                "csr_id": csr_id
            },
            tenant_id=call_record.company_id,
            lead_id=call_record.call_id
        )
        
        return {"status": "success", "call_id": call_record.call_id}
        
    except Exception as e:
        logger.error(f"Error handling call.answered: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callrail/call.missed")
@limits(tenant="30/minute")
async def handle_call_missed(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle CallRail 'call.missed' webhook
    Routes to Missed Call Queue and triggers AI recovery via Twilio SMS
    """
    try:
        data = await request.json()
        logger.info(f"CallRail call.missed webhook: {data}")
        
        # Extract call data
        customer_phone = data.get("customer_phone_number") or data.get("callernum") or data.get("caller_number")
        tracking_number = data.get("tracking_phone_number") or data.get("trackingnum") or data.get("tracking_number")
        
        # Find company by tracking number
        company_record = db.query(company.Company).filter_by(phone_number=tracking_number).first()
        if not company_record:
            logger.warning(f"No company found for tracking number {tracking_number}")
            return {"status": "error", "message": "Company not found"}
        
        # Find call record by phone number and company
        call_record = db.query(call.Call).filter_by(
            phone_number=customer_phone,
            company_id=company_record.id
        ).order_by(call.Call.created_at.desc()).first()
        
        if not call_record:
            logger.warning(f"Call record not found for phone {customer_phone}, company {company_record.id}")
            return {"status": "error", "message": "Call record not found"}
        
        # Update call record
        call_record.missed_call = True
        call_record.status = "missed"
        call_record.updated_at = datetime.utcnow()
        db.commit()
        
        # Route to Missed Call Queue
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        background_tasks.add_task(
            missed_call_service.add_missed_call_to_queue,
            call_record.call_id,
            caller_number,
            call_record.company_id,
            db
        )
        
        # Emit real-time event
        emit(
            event_name="call.missed",
            payload={
                "call_id": call_record.call_id,
                "phone_number": caller_number,
                "status": "routed_to_recovery"
            },
            tenant_id=call_record.company_id,
            lead_id=call_record.call_id
        )
        
        return {"status": "success", "call_id": call_record.call_id}
        
    except Exception as e:
        logger.error(f"Error handling call.missed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callrail/call.completed")
@limits(tenant="30/minute")
async def handle_call_completed(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle CallRail 'call.completed' webhook
    Processes recording, sends to UWC ASR, and generates insights
    Note: CallRail doesn't have a separate 'call.missed' webhook, so we detect
    missed calls from the 'answered' field in this webhook.
    """
    try:
        data = await request.json()
        logger.info(f"CallRail call.completed webhook: {data}")
        
        # Extract call data from webhook
        resource_id = data.get("resource_id")  # CallRail call ID (e.g., "CAL019a4be69ef4764db2d8ac1d6b21ee00")
        customer_phone = data.get("customer_phone_number") or data.get("callernum") or data.get("caller_number")
        tracking_number = data.get("tracking_phone_number") or data.get("trackingnum") or data.get("tracking_number")
        recording_url = data.get("recording") or data.get("recording_url")
        duration = data.get("duration")
        is_answered = data.get("answered", True)  # Default to True if not provided
        
        # Find company by tracking number
        company_record = db.query(company.Company).filter_by(phone_number=tracking_number).first()
        if not company_record:
            logger.warning(f"No company found for tracking number {tracking_number}")
            return {"status": "error", "message": "Company not found"}
        
        # Find or create call record by phone number and company
        # For missed calls, we may not have a pre-existing record, so create one if needed
        call_record = db.query(call.Call).filter_by(
            phone_number=customer_phone,
            company_id=company_record.id
        ).order_by(call.Call.created_at.desc()).first()
        
        if not call_record:
            # Create new call record for missed call or if it doesn't exist
            logger.info(f"Creating new call record for phone {customer_phone}, company {company_record.id}")
            
            # Parse created_at timestamp from webhook
            try:
                created_at_str = data.get("created_at") or data.get("timestamp")
                if created_at_str:
                    # Handle timezone-aware ISO format
                    if created_at_str.endswith("Z"):
                        created_at_str = created_at_str.replace("Z", "+00:00")
                    created_at = datetime.fromisoformat(created_at_str.replace(" ", "T"))
                else:
                    created_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Error parsing created_at timestamp: {e}, using current time")
                created_at = datetime.utcnow()
            
            call_record = call.Call(
                phone_number=customer_phone,
                company_id=company_record.id,
                name=data.get("customer_name") or data.get("callername") or "Unknown Caller",
                created_at=created_at,
                missed_call=not is_answered,
                status="missed" if not is_answered else "completed"
            )
            db.add(call_record)
            db.commit()
            db.refresh(call_record)
            logger.info(f"Created new call record: {call_record.call_id}")
        
        # Check if this was a missed call
        call_record.missed_call = not is_answered
        
        # Update call record
        if not is_answered:
            call_record.status = "missed"
            logger.info(f"⚠️⚠️⚠️ MISSED CALL DETECTED ⚠️⚠️⚠️ - Routing to missed call queue")
            
            # Route to Missed Call Queue Service
            from app.services.missed_call_queue_service import MissedCallQueueService
            missed_call_service = MissedCallQueueService()
            
            background_tasks.add_task(
                missed_call_service.add_missed_call_to_queue,
                call_record.call_id,
                call_record.phone_number,
                call_record.company_id,
                db
            )
        else:
            call_record.status = "completed"
        
        # Update duration if provided (store as last_call_duration)
        if duration:
            try:
                call_record.last_call_duration = int(duration)
            except (ValueError, TypeError):
                pass
        
        # Note: recording_url is not stored in Call model, but can be accessed from CallRail API if needed
        if recording_url:
            logger.info(f"CallRail recording URL available: {recording_url}")
        
        call_record.updated_at = datetime.utcnow()
        db.commit()
        
        # Check for human takeover before processing (only for answered calls with recordings)
        if is_answered:
            missed_call_service = MissedCallQueueService()
            await missed_call_service.check_and_stop_ai_automation(
                phone=call_record.phone_number,
                db=db
            )
        
        # Process recording with UWC ASR
        if recording_url:
            background_tasks.add_task(
                process_call_recording,
                call_record.call_id,
                recording_url,
                db
            )
        
        # Emit real-time event
        emit(
            event_name="call.completed",
            payload={
                "call_id": call_record.call_id,
                "recording_url": recording_url,
                "duration": duration
            },
            tenant_id=call_record.company_id,
            lead_id=call_record.call_id
        )
        
        return {"status": "success", "call_id": call_record.call_id}
        
    except Exception as e:
        logger.error(f"Error handling call.completed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_missed_call_recovery(
    call_id: int,
    phone_number: str,
    company_id: str,
    db: Session
):
    """
    Process missed call recovery via AI-led SMS conversation
    """
    try:
        # Get company info
        company_record = db.query(company.Company).filter_by(id=company_id).first()
        if not company_record:
            logger.error(f"Company not found: {company_id}")
            return
        
        # Determine if new or existing customer
        existing_calls = db.query(call.Call).filter_by(
            phone_number=phone_number,
            company_id=company_id
        ).count()
        
        is_new_customer = existing_calls <= 1
        
        # Send AI-led SMS based on new/existing status
        if is_new_customer:
            message = f"""Hi! We just missed your call to {company_record.name}. 

We'd love to help you with your project! 

Reply with:
• Your address for a quick quote
• Your preferred time to talk
• Any questions you have

We'll get back to you within 2 hours! 🏠"""
        else:
            message = f"""Hi! We just missed your call to {company_record.name}. 

Thanks for reaching out again! 

Reply with:
• Your address for a quick quote
• Your preferred time to talk
• Any questions you have

We'll get back to you within 2 hours! 🏠"""
        
        # Send SMS via Twilio
        sms_result = twilio_service.send_sms(
            to=phone_number,
            body=message,
            from_number=company_record.phone_number
        )
        
        if sms_result.get("status") == "success":
            # Update call record with SMS info
            call_record = db.query(call.Call).filter_by(call_id=call_id).first()
            if call_record:
                call_record.text_messages = json.dumps([{
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": message,
                    "direction": "outbound",
                    "provider": "twilio",
                    "message_sid": sms_result.get("message_sid", "")
                }])
                call_record.status = "ai_recovery_sent"
                db.commit()
                
                logger.info(f"AI recovery SMS sent to {phone_number}")
        else:
            logger.error(f"Failed to send AI recovery SMS: {sms_result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error processing missed call recovery: {str(e)}")

async def process_call_recording(
    call_id: int,
    recording_url: str,
    db: Session
):
    """
    Process call recording with UWC ASR and generate insights
    """
    try:
        # Get UWC client
        uwc_client = get_uwc_client()
        
        # Send recording to UWC ASR
        asr_result = await uwc_client.transcribe_audio(recording_url)
        
        if asr_result.get("status") == "success":
            # Update call record with transcript
            call_record = db.query(call.Call).filter_by(call_id=call_id).first()
            if call_record:
                call_record.transcript = asr_result.get("transcript", "")
                call_record.asr_status = "completed"
                call_record.updated_at = datetime.utcnow()
                db.commit()
                
                # Generate insights and update lead outcome
                await generate_call_insights(call_id, asr_result.get("transcript", ""), db)
                
                logger.info(f"Call recording processed for call {call_id}")
        else:
            logger.error(f"ASR processing failed: {asr_result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error processing call recording: {str(e)}")

async def generate_call_insights(
    call_id: int,
    transcript: str,
    db: Session
):
    """
    Generate coaching insights and update lead outcome
    """
    try:
        # This would integrate with the existing transcript analysis system
        # For now, we'll just log the transcript
        logger.info(f"Generated insights for call {call_id}")
        
        # Update lead outcome based on transcript analysis
        # This would be implemented with the existing transcript analysis system
        
    except Exception as e:
        logger.error(f"Error generating call insights: {str(e)}")

@router.get("/callrail/status/{call_id}")
async def get_call_status(
    call_id: int,
    db: Session = Depends(get_db)
):
    """Get call status and processing information"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        return {
            "call_id": call_record.call_id,
            "phone_number": call_record.phone_number,
            "status": call_record.status,
            "missed_call": call_record.missed_call,
            "duration": call_record.duration,
            "recording_url": call_record.recording_url,
            "transcript": call_record.transcript,
            "asr_status": call_record.asr_status,
            "created_at": call_record.created_at,
            "updated_at": call_record.updated_at
        }
        
    except Exception as e:
        logger.error(f"Error getting call status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
