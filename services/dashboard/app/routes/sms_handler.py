"""
Enhanced SMS Handler for OttoAI Platform
Handles inbound text messages from CallRail and Twilio
Creates leads automatically for new text conversations
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import call, company
from app.services.twilio_service import TwilioService
from app.services.uwc_client import get_uwc_client
from app.middleware.rate_limiter import limits
from app.services.idempotency import with_idempotency
from app.services.domain_entities import ensure_contact_card_and_lead
from app.realtime.bus import emit
from datetime import datetime
import json
import logging
from typing import Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# API router for authenticated endpoints (with /api/v1 prefix)
router = APIRouter(prefix="/api/v1/sms", tags=["sms"])

# Webhook router for external services (without /api/v1 prefix)
webhook_router = APIRouter(prefix="/sms", tags=["sms-webhooks"])

# Initialize services
twilio_service = TwilioService()

class SMSWebhookData(BaseModel):
    """SMS webhook data structure"""
    from_number: str
    to_number: str
    message_body: str
    message_sid: str
    provider: str = "twilio"  # or "callrail"

class SMSResponse(BaseModel):
    """SMS response structure"""
    status: str
    call_id: Optional[int] = None
    lead_created: bool = False
    auto_reply_sent: bool = False

@webhook_router.post("/callrail-webhook")
@limits(tenant="30/minute")
async def handle_callrail_sms_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle inbound SMS messages from CallRail
    CallRail sends SMS webhooks when customers text tracking numbers
    """
    try:
        # Parse CallRail SMS webhook data
        data = await request.json()
        logger.info(f"CallRail SMS webhook received: {data}")
        
        # Extract SMS data from CallRail webhook
        from_number = data.get("from_number") or data.get("caller_number")
        to_number = data.get("to_number") or data.get("tracking_number")
        message_body = data.get("message") or data.get("text")
        message_sid = data.get("message_id") or data.get("id")
        
        if not all([from_number, to_number, message_body]):
            raise HTTPException(status_code=400, detail="Missing required SMS data")
        
        # Check if this is a response to a missed call queue
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # Try to handle as missed call response first
        queue_result = await missed_call_service.handle_customer_response(
            phone=from_number,
            response_text=message_body,
            db=db
        )
        
        if queue_result:
            # This was handled by the missed call queue system
            return SMSResponse(
                status="missed_call_response",
                call_id=queue_result.call_id,
                lead_created=False,
                auto_reply_sent=False
            )
        
        # Check if human has taken over any active queue entries for this phone
        await missed_call_service.check_and_stop_ai_automation(
            phone=from_number,
            db=db
        )
        
        # If not a missed call response, process as regular SMS
        result = await process_inbound_sms(
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            message_sid=message_sid,
            provider="callrail",
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"CallRail SMS webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"SMS processing failed: {str(e)}")

@webhook_router.post("/twilio-webhook")
@limits(tenant="30/minute")
async def handle_twilio_sms_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle inbound SMS messages from Twilio
    Enhanced version of existing Twilio webhook
    """
    try:
        # Parse form data from Twilio
        form_data = await request.form()
        
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        message_body = form_data.get("Body")
        message_sid = form_data.get("MessageSid")
        
        logger.info(f"Twilio SMS webhook received from {from_number}: {message_body}")
        
        if not all([from_number, to_number, message_body]):
            raise HTTPException(status_code=400, detail="Missing required SMS data")
        
        # Check if this is a response to a missed call queue
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # Try to handle as missed call response first
        queue_result = await missed_call_service.handle_customer_response(
            phone=from_number,
            response_text=message_body,
            db=db
        )
        
        if queue_result:
            # This was handled by the missed call queue system
            return SMSResponse(
                status="missed_call_response",
                call_id=queue_result.call_id,
                lead_created=False,
                auto_reply_sent=False
            )
        
        # Check if human has taken over any active queue entries for this phone
        await missed_call_service.check_and_stop_ai_automation(
            phone=from_number,
            db=db
        )
        
        # If not a missed call response, process as regular SMS
        result = await process_inbound_sms(
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            message_sid=message_sid,
            provider="twilio",
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Twilio SMS webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"SMS processing failed: {str(e)}")

async def process_inbound_sms(
    from_number: str,
    to_number: str,
    message_body: str,
    message_sid: str,
    provider: str,
    db: Session
) -> SMSResponse:
    """
    Process inbound SMS message and create/update lead
    """
    try:
        # Find company by tracking number
        company_record = db.query(company.Company).filter_by(phone_number=to_number).first()
        if not company_record:
            logger.warning(f"No company found for tracking number {to_number}")
            return SMSResponse(
                status="error",
                lead_created=False,
                auto_reply_sent=False
            )
        
        logger.info(f"Processing SMS for company: {company_record.name}")
        
        # Check if this is an existing conversation
        existing_call = db.query(call.Call).filter_by(
            phone_number=from_number,
            company_id=company_record.id
        ).first()
        
        contact_card, lead = ensure_contact_card_and_lead(
            db,
            company_id=company_record.id,
            phone_number=from_number,
        )

        if existing_call:
            # Update existing conversation
            logger.info(f"Updating existing conversation for {from_number}")
            call_id = existing_call.call_id
            if not existing_call.contact_card_id:
                existing_call.contact_card_id = contact_card.id
            if not existing_call.lead_id:
                existing_call.lead_id = lead.id
            db.commit()
            
            # Add message to conversation
            await add_message_to_conversation(
                call_id=call_id,
                message_body=message_body,
                direction="inbound",
                provider=provider,
                message_sid=message_sid,
                db=db
            )
            
            # Send auto-reply if it's the first message in this conversation
            auto_reply_sent = await send_auto_reply_if_needed(
                call_id=call_id,
                from_number=from_number,
                company_record=company_record,
                db=db
            )
            
            return SMSResponse(
                status="updated",
                call_id=call_id,
                lead_created=False,
                auto_reply_sent=auto_reply_sent
            )
        else:
            # Create new lead/conversation
            logger.info(f"Creating new lead for {from_number}")
            
            new_call = call.Call(
                phone_number=from_number,
                company_id=company_record.id,
                contact_card_id=contact_card.id,
                lead_id=lead.id,
                created_at=datetime.utcnow(),
                missed_call=False,  # SMS is not a missed call
                text_messages=json.dumps([{
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": message_body,
                    "direction": "inbound",
                    "provider": provider,
                    "message_sid": message_sid
                }]),
                mobile_texts_count=1
            )
            
            db.add(new_call)
            db.commit()
            db.refresh(new_call)
            
            call_id = new_call.call_id
            logger.info(f"New SMS lead created: {call_id}")
            
            # Send welcome auto-reply
            auto_reply_sent = await send_welcome_message(
                to_number=from_number,
                company_record=company_record,
                call_id=call_id,
                db=db
            )
            
            # Emit real-time event
            emit(
                event_name="sms.lead.created",
                payload={
                    "call_id": call_id,
                    "phone_number": from_number,
                    "company_id": str(company_record.id),
                    "message": message_body,
                    "provider": provider
                },
                tenant_id=company_record.id,
                lead_id=call_id
            )
            
            return SMSResponse(
                status="created",
                call_id=call_id,
                lead_created=True,
                auto_reply_sent=auto_reply_sent
            )
            
    except Exception as e:
        logger.error(f"Error processing SMS: {str(e)}")
        raise

async def add_message_to_conversation(
    call_id: int,
    message_body: str,
    direction: str,
    provider: str,
    message_sid: str,
    db: Session
):
    """Add message to existing conversation"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Parse existing messages
        current_messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        
        # Add new message
        current_messages.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message_body,
            "direction": direction,
            "provider": provider,
            "message_sid": message_sid
        })
        
        # Update call record
        call_record.text_messages = json.dumps(current_messages)
        call_record.mobile_texts_count = (call_record.mobile_texts_count or 0) + 1
        call_record.updated_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Message added to conversation {call_id}")
        
    except Exception as e:
        logger.error(f"Error adding message to conversation: {str(e)}")
        raise

async def send_auto_reply_if_needed(
    call_id: int,
    from_number: str,
    company_record: company.Company,
    db: Session
) -> bool:
    """Send auto-reply if this is the first message in conversation"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            return False
        
        # Check if this is the first inbound message
        messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        inbound_messages = [msg for msg in messages if msg.get("direction") == "inbound"]
        
        if len(inbound_messages) == 1:  # First inbound message
            return await send_welcome_message(
                to_number=from_number,
                company_record=company_record,
                call_id=call_id,
                db=db
            )
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking auto-reply: {str(e)}")
        return False

async def send_welcome_message(
    to_number: str,
    company_record: company.Company,
    call_id: int,
    db: Session
) -> bool:
    """Send welcome message to new SMS lead"""
    try:
        # Create welcome message
        welcome_message = (
            f"Hi! Thanks for reaching out to {company_record.name}.\n\n"
            "We received your message and will get back to you shortly.\n\n"
            "In the meantime, you can:\n"
            "- Reply with your address for a quick quote\n"
            "- Let us know your preferred appointment time\n"
            "- Ask any questions about our services\n\n"
            "We're here to help!"
        )
        
        # Send SMS via Twilio
        sms_result = await twilio_service.send_sms(
            to=to_number,
            body=welcome_message,
            from_number=company_record.phone_number
        )
        
        if sms_result.get("status") == "success":
            # Add outbound message to conversation
            await add_message_to_conversation(
                call_id=call_id,
                message_body=welcome_message,
                direction="outbound",
                provider="twilio",
                message_sid=sms_result.get("message_sid", ""),
                db=db
            )
            
            logger.info(f"Welcome message sent to {to_number}")
            return True
        else:
            logger.error(f"Failed to send welcome message: {sms_result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending welcome message: {str(e)}")
        return False

@router.get("/conversations/{call_id}")
async def get_sms_conversation(
    call_id: int,
    db: Session = Depends(get_db)
):
    """Get SMS conversation history"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        
        return {
            "call_id": call_id,
            "phone_number": call_record.phone_number,
            "company_id": call_record.company_id,
            "total_messages": len(messages),
            "messages": messages
        }
        
    except Exception as e:
        logger.error(f"Error getting SMS conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send")
async def send_sms_to_customer(
    call_id: int,
    message: str,
    db: Session = Depends(get_db)
):
    """Send SMS to customer"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        company_record = db.query(company.Company).filter_by(id=call_record.company_id).first()
        if not company_record:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check if human has taken over and stop AI automation
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # This human SMS will trigger takeover detection
        await missed_call_service.check_and_stop_ai_automation(
            phone=call_record.phone_number,
            db=db
        )
        
        # Send SMS
        sms_result = await twilio_service.send_sms(
            to=call_record.phone_number,
            body=message,
            from_number=company_record.phone_number
        )
        
        if sms_result.get("status") == "success":
            # Add to conversation with human marker
            await add_message_to_conversation(
                call_id=call_id,
                message_body=message,
                direction="outbound",
                provider="twilio",
                message_sid=sms_result.get("message_sid", ""),
                db=db
            )
            
            # Mark this as human-generated message to prevent AI takeover detection
            call_record = db.query(call.Call).filter_by(call_id=call_id).first()
            if call_record:
                messages = json.loads(call_record.text_messages) if call_record.text_messages else []
                if messages:
                    messages[-1]["human_generated"] = True
                    call_record.text_messages = json.dumps(messages)
                    db.commit()
            
            return {"status": "sent", "message_sid": sms_result.get("message_sid")}
        else:
            raise HTTPException(status_code=500, detail=f"SMS send failed: {sms_result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

Handles inbound text messages from CallRail and Twilio
Creates leads automatically for new text conversations
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import call, company
from app.services.twilio_service import TwilioService
from app.services.uwc_client import get_uwc_client
from app.middleware.rate_limiter import limits
from app.services.idempotency import with_idempotency
from app.services.domain_entities import ensure_contact_card_and_lead
from app.realtime.bus import emit
from datetime import datetime
import json
import logging
from typing import Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# API router for authenticated endpoints (with /api/v1 prefix)
router = APIRouter(prefix="/api/v1/sms", tags=["sms"])

# Webhook router for external services (without /api/v1 prefix)
webhook_router = APIRouter(prefix="/sms", tags=["sms-webhooks"])

# Initialize services
twilio_service = TwilioService()

class SMSWebhookData(BaseModel):
    """SMS webhook data structure"""
    from_number: str
    to_number: str
    message_body: str
    message_sid: str
    provider: str = "twilio"  # or "callrail"

class SMSResponse(BaseModel):
    """SMS response structure"""
    status: str
    call_id: Optional[int] = None
    lead_created: bool = False
    auto_reply_sent: bool = False

@webhook_router.post("/callrail-webhook")
@limits(tenant="30/minute")
async def handle_callrail_sms_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle inbound SMS messages from CallRail
    CallRail sends SMS webhooks when customers text tracking numbers
    """
    try:
        # Parse CallRail SMS webhook data
        data = await request.json()
        logger.info(f"CallRail SMS webhook received: {data}")
        
        # Extract SMS data from CallRail webhook
        from_number = data.get("from_number") or data.get("caller_number")
        to_number = data.get("to_number") or data.get("tracking_number")
        message_body = data.get("message") or data.get("text")
        message_sid = data.get("message_id") or data.get("id")
        
        if not all([from_number, to_number, message_body]):
            raise HTTPException(status_code=400, detail="Missing required SMS data")
        
        # Check if this is a response to a missed call queue
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # Try to handle as missed call response first
        queue_result = await missed_call_service.handle_customer_response(
            phone=from_number,
            response_text=message_body,
            db=db
        )
        
        if queue_result:
            # This was handled by the missed call queue system
            return SMSResponse(
                status="missed_call_response",
                call_id=queue_result.call_id,
                lead_created=False,
                auto_reply_sent=False
            )
        
        # Check if human has taken over any active queue entries for this phone
        await missed_call_service.check_and_stop_ai_automation(
            phone=from_number,
            db=db
        )
        
        # If not a missed call response, process as regular SMS
        result = await process_inbound_sms(
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            message_sid=message_sid,
            provider="callrail",
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"CallRail SMS webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"SMS processing failed: {str(e)}")

@webhook_router.post("/twilio-webhook")
@limits(tenant="30/minute")
async def handle_twilio_sms_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle inbound SMS messages from Twilio
    Enhanced version of existing Twilio webhook
    """
    try:
        # Parse form data from Twilio
        form_data = await request.form()
        
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        message_body = form_data.get("Body")
        message_sid = form_data.get("MessageSid")
        
        logger.info(f"Twilio SMS webhook received from {from_number}: {message_body}")
        
        if not all([from_number, to_number, message_body]):
            raise HTTPException(status_code=400, detail="Missing required SMS data")
        
        # Check if this is a response to a missed call queue
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # Try to handle as missed call response first
        queue_result = await missed_call_service.handle_customer_response(
            phone=from_number,
            response_text=message_body,
            db=db
        )
        
        if queue_result:
            # This was handled by the missed call queue system
            return SMSResponse(
                status="missed_call_response",
                call_id=queue_result.call_id,
                lead_created=False,
                auto_reply_sent=False
            )
        
        # Check if human has taken over any active queue entries for this phone
        await missed_call_service.check_and_stop_ai_automation(
            phone=from_number,
            db=db
        )
        
        # If not a missed call response, process as regular SMS
        result = await process_inbound_sms(
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            message_sid=message_sid,
            provider="twilio",
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Twilio SMS webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"SMS processing failed: {str(e)}")

async def process_inbound_sms(
    from_number: str,
    to_number: str,
    message_body: str,
    message_sid: str,
    provider: str,
    db: Session
) -> SMSResponse:
    """
    Process inbound SMS message and create/update lead
    """
    try:
        # Find company by tracking number
        company_record = db.query(company.Company).filter_by(phone_number=to_number).first()
        if not company_record:
            logger.warning(f"No company found for tracking number {to_number}")
            return SMSResponse(
                status="error",
                lead_created=False,
                auto_reply_sent=False
            )
        
        logger.info(f"Processing SMS for company: {company_record.name}")
        
        # Check if this is an existing conversation
        existing_call = db.query(call.Call).filter_by(
            phone_number=from_number,
            company_id=company_record.id
        ).first()
        
        contact_card, lead = ensure_contact_card_and_lead(
            db,
            company_id=company_record.id,
            phone_number=from_number,
        )

        if existing_call:
            # Update existing conversation
            logger.info(f"Updating existing conversation for {from_number}")
            call_id = existing_call.call_id
            if not existing_call.contact_card_id:
                existing_call.contact_card_id = contact_card.id
            if not existing_call.lead_id:
                existing_call.lead_id = lead.id
            db.commit()
            
            # Add message to conversation
            await add_message_to_conversation(
                call_id=call_id,
                message_body=message_body,
                direction="inbound",
                provider=provider,
                message_sid=message_sid,
                db=db
            )
            
            # Send auto-reply if it's the first message in this conversation
            auto_reply_sent = await send_auto_reply_if_needed(
                call_id=call_id,
                from_number=from_number,
                company_record=company_record,
                db=db
            )
            
            return SMSResponse(
                status="updated",
                call_id=call_id,
                lead_created=False,
                auto_reply_sent=auto_reply_sent
            )
        else:
            # Create new lead/conversation
            logger.info(f"Creating new lead for {from_number}")
            
            new_call = call.Call(
                phone_number=from_number,
                company_id=company_record.id,
                contact_card_id=contact_card.id,
                lead_id=lead.id,
                created_at=datetime.utcnow(),
                missed_call=False,  # SMS is not a missed call
                text_messages=json.dumps([{
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": message_body,
                    "direction": "inbound",
                    "provider": provider,
                    "message_sid": message_sid
                }]),
                mobile_texts_count=1
            )
            
            db.add(new_call)
            db.commit()
            db.refresh(new_call)
            
            call_id = new_call.call_id
            logger.info(f"New SMS lead created: {call_id}")
            
            # Send welcome auto-reply
            auto_reply_sent = await send_welcome_message(
                to_number=from_number,
                company_record=company_record,
                call_id=call_id,
                db=db
            )
            
            # Emit real-time event
            emit(
                event_name="sms.lead.created",
                payload={
                    "call_id": call_id,
                    "phone_number": from_number,
                    "company_id": str(company_record.id),
                    "message": message_body,
                    "provider": provider
                },
                tenant_id=company_record.id,
                lead_id=call_id
            )
            
            return SMSResponse(
                status="created",
                call_id=call_id,
                lead_created=True,
                auto_reply_sent=auto_reply_sent
            )
            
    except Exception as e:
        logger.error(f"Error processing SMS: {str(e)}")
        raise

async def add_message_to_conversation(
    call_id: int,
    message_body: str,
    direction: str,
    provider: str,
    message_sid: str,
    db: Session
):
    """Add message to existing conversation"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Parse existing messages
        current_messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        
        # Add new message
        current_messages.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message_body,
            "direction": direction,
            "provider": provider,
            "message_sid": message_sid
        })
        
        # Update call record
        call_record.text_messages = json.dumps(current_messages)
        call_record.mobile_texts_count = (call_record.mobile_texts_count or 0) + 1
        call_record.updated_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Message added to conversation {call_id}")
        
    except Exception as e:
        logger.error(f"Error adding message to conversation: {str(e)}")
        raise

async def send_auto_reply_if_needed(
    call_id: int,
    from_number: str,
    company_record: company.Company,
    db: Session
) -> bool:
    """Send auto-reply if this is the first message in conversation"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            return False
        
        # Check if this is the first inbound message
        messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        inbound_messages = [msg for msg in messages if msg.get("direction") == "inbound"]
        
        if len(inbound_messages) == 1:  # First inbound message
            return await send_welcome_message(
                to_number=from_number,
                company_record=company_record,
                call_id=call_id,
                db=db
            )
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking auto-reply: {str(e)}")
        return False

async def send_welcome_message(
    to_number: str,
    company_record: company.Company,
    call_id: int,
    db: Session
) -> bool:
    """Send welcome message to new SMS lead"""
    try:
        # Create welcome message
        welcome_message = (
            f"Hi! Thanks for reaching out to {company_record.name}.\n\n"
            "We received your message and will get back to you shortly.\n\n"
            "In the meantime, you can:\n"
            "- Reply with your address for a quick quote\n"
            "- Let us know your preferred appointment time\n"
            "- Ask any questions about our services\n\n"
            "We're here to help!"
        )
        
        # Send SMS via Twilio
        sms_result = await twilio_service.send_sms(
            to=to_number,
            body=welcome_message,
            from_number=company_record.phone_number
        )
        
        if sms_result.get("status") == "success":
            # Add outbound message to conversation
            await add_message_to_conversation(
                call_id=call_id,
                message_body=welcome_message,
                direction="outbound",
                provider="twilio",
                message_sid=sms_result.get("message_sid", ""),
                db=db
            )
            
            logger.info(f"Welcome message sent to {to_number}")
            return True
        else:
            logger.error(f"Failed to send welcome message: {sms_result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending welcome message: {str(e)}")
        return False

@router.get("/conversations/{call_id}")
async def get_sms_conversation(
    call_id: int,
    db: Session = Depends(get_db)
):
    """Get SMS conversation history"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        
        return {
            "call_id": call_id,
            "phone_number": call_record.phone_number,
            "company_id": call_record.company_id,
            "total_messages": len(messages),
            "messages": messages
        }
        
    except Exception as e:
        logger.error(f"Error getting SMS conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send")
async def send_sms_to_customer(
    call_id: int,
    message: str,
    db: Session = Depends(get_db)
):
    """Send SMS to customer"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        company_record = db.query(company.Company).filter_by(id=call_record.company_id).first()
        if not company_record:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check if human has taken over and stop AI automation
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # This human SMS will trigger takeover detection
        await missed_call_service.check_and_stop_ai_automation(
            phone=call_record.phone_number,
            db=db
        )
        
        # Send SMS
        sms_result = await twilio_service.send_sms(
            to=call_record.phone_number,
            body=message,
            from_number=company_record.phone_number
        )
        
        if sms_result.get("status") == "success":
            # Add to conversation with human marker
            await add_message_to_conversation(
                call_id=call_id,
                message_body=message,
                direction="outbound",
                provider="twilio",
                message_sid=sms_result.get("message_sid", ""),
                db=db
            )
            
            # Mark this as human-generated message to prevent AI takeover detection
            call_record = db.query(call.Call).filter_by(call_id=call_id).first()
            if call_record:
                messages = json.loads(call_record.text_messages) if call_record.text_messages else []
                if messages:
                    messages[-1]["human_generated"] = True
                    call_record.text_messages = json.dumps(messages)
                    db.commit()
            
            return {"status": "sent", "message_sid": sms_result.get("message_sid")}
        else:
            raise HTTPException(status_code=500, detail=f"SMS send failed: {sms_result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

Handles inbound text messages from CallRail and Twilio
Creates leads automatically for new text conversations
"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import call, company
from app.services.twilio_service import TwilioService
from app.services.uwc_client import get_uwc_client
from app.middleware.rate_limiter import limits
from app.services.idempotency import with_idempotency
from app.services.domain_entities import ensure_contact_card_and_lead
from app.realtime.bus import emit
from datetime import datetime
import json
import logging
from typing import Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# API router for authenticated endpoints (with /api/v1 prefix)
router = APIRouter(prefix="/api/v1/sms", tags=["sms"])

# Webhook router for external services (without /api/v1 prefix)
webhook_router = APIRouter(prefix="/sms", tags=["sms-webhooks"])

# Initialize services
twilio_service = TwilioService()

class SMSWebhookData(BaseModel):
    """SMS webhook data structure"""
    from_number: str
    to_number: str
    message_body: str
    message_sid: str
    provider: str = "twilio"  # or "callrail"

class SMSResponse(BaseModel):
    """SMS response structure"""
    status: str
    call_id: Optional[int] = None
    lead_created: bool = False
    auto_reply_sent: bool = False

@webhook_router.post("/callrail-webhook")
@limits(tenant="30/minute")
async def handle_callrail_sms_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle inbound SMS messages from CallRail
    CallRail sends SMS webhooks when customers text tracking numbers
    """
    try:
        # Parse CallRail SMS webhook data
        data = await request.json()
        logger.info(f"CallRail SMS webhook received: {data}")
        
        # Extract SMS data from CallRail webhook
        from_number = data.get("from_number") or data.get("caller_number")
        to_number = data.get("to_number") or data.get("tracking_number")
        message_body = data.get("message") or data.get("text")
        message_sid = data.get("message_id") or data.get("id")
        
        if not all([from_number, to_number, message_body]):
            raise HTTPException(status_code=400, detail="Missing required SMS data")
        
        # Check if this is a response to a missed call queue
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # Try to handle as missed call response first
        queue_result = await missed_call_service.handle_customer_response(
            phone=from_number,
            response_text=message_body,
            db=db
        )
        
        if queue_result:
            # This was handled by the missed call queue system
            return SMSResponse(
                status="missed_call_response",
                call_id=queue_result.call_id,
                lead_created=False,
                auto_reply_sent=False
            )
        
        # Check if human has taken over any active queue entries for this phone
        await missed_call_service.check_and_stop_ai_automation(
            phone=from_number,
            db=db
        )
        
        # If not a missed call response, process as regular SMS
        result = await process_inbound_sms(
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            message_sid=message_sid,
            provider="callrail",
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"CallRail SMS webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"SMS processing failed: {str(e)}")

@webhook_router.post("/twilio-webhook")
@limits(tenant="30/minute")
async def handle_twilio_sms_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle inbound SMS messages from Twilio
    Enhanced version of existing Twilio webhook
    """
    try:
        # Parse form data from Twilio
        form_data = await request.form()
        
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        message_body = form_data.get("Body")
        message_sid = form_data.get("MessageSid")
        
        logger.info(f"Twilio SMS webhook received from {from_number}: {message_body}")
        
        if not all([from_number, to_number, message_body]):
            raise HTTPException(status_code=400, detail="Missing required SMS data")
        
        # Check if this is a response to a missed call queue
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # Try to handle as missed call response first
        queue_result = await missed_call_service.handle_customer_response(
            phone=from_number,
            response_text=message_body,
            db=db
        )
        
        if queue_result:
            # This was handled by the missed call queue system
            return SMSResponse(
                status="missed_call_response",
                call_id=queue_result.call_id,
                lead_created=False,
                auto_reply_sent=False
            )
        
        # Check if human has taken over any active queue entries for this phone
        await missed_call_service.check_and_stop_ai_automation(
            phone=from_number,
            db=db
        )
        
        # If not a missed call response, process as regular SMS
        result = await process_inbound_sms(
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            message_sid=message_sid,
            provider="twilio",
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Twilio SMS webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"SMS processing failed: {str(e)}")

async def process_inbound_sms(
    from_number: str,
    to_number: str,
    message_body: str,
    message_sid: str,
    provider: str,
    db: Session
) -> SMSResponse:
    """
    Process inbound SMS message and create/update lead
    """
    try:
        # Find company by tracking number
        company_record = db.query(company.Company).filter_by(phone_number=to_number).first()
        if not company_record:
            logger.warning(f"No company found for tracking number {to_number}")
            return SMSResponse(
                status="error",
                lead_created=False,
                auto_reply_sent=False
            )
        
        logger.info(f"Processing SMS for company: {company_record.name}")
        
        # Check if this is an existing conversation
        existing_call = db.query(call.Call).filter_by(
            phone_number=from_number,
            company_id=company_record.id
        ).first()
        
        contact_card, lead = ensure_contact_card_and_lead(
            db,
            company_id=company_record.id,
            phone_number=from_number,
        )

        if existing_call:
            # Update existing conversation
            logger.info(f"Updating existing conversation for {from_number}")
            call_id = existing_call.call_id
            if not existing_call.contact_card_id:
                existing_call.contact_card_id = contact_card.id
            if not existing_call.lead_id:
                existing_call.lead_id = lead.id
            db.commit()
            
            # Add message to conversation
            await add_message_to_conversation(
                call_id=call_id,
                message_body=message_body,
                direction="inbound",
                provider=provider,
                message_sid=message_sid,
                db=db
            )
            
            # Send auto-reply if it's the first message in this conversation
            auto_reply_sent = await send_auto_reply_if_needed(
                call_id=call_id,
                from_number=from_number,
                company_record=company_record,
                db=db
            )
            
            return SMSResponse(
                status="updated",
                call_id=call_id,
                lead_created=False,
                auto_reply_sent=auto_reply_sent
            )
        else:
            # Create new lead/conversation
            logger.info(f"Creating new lead for {from_number}")
            
            new_call = call.Call(
                phone_number=from_number,
                company_id=company_record.id,
                contact_card_id=contact_card.id,
                lead_id=lead.id,
                created_at=datetime.utcnow(),
                missed_call=False,  # SMS is not a missed call
                text_messages=json.dumps([{
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": message_body,
                    "direction": "inbound",
                    "provider": provider,
                    "message_sid": message_sid
                }]),
                mobile_texts_count=1
            )
            
            db.add(new_call)
            db.commit()
            db.refresh(new_call)
            
            call_id = new_call.call_id
            logger.info(f"New SMS lead created: {call_id}")
            
            # Send welcome auto-reply
            auto_reply_sent = await send_welcome_message(
                to_number=from_number,
                company_record=company_record,
                call_id=call_id,
                db=db
            )
            
            # Emit real-time event
            emit(
                event_name="sms.lead.created",
                payload={
                    "call_id": call_id,
                    "phone_number": from_number,
                    "company_id": str(company_record.id),
                    "message": message_body,
                    "provider": provider
                },
                tenant_id=company_record.id,
                lead_id=call_id
            )
            
            return SMSResponse(
                status="created",
                call_id=call_id,
                lead_created=True,
                auto_reply_sent=auto_reply_sent
            )
            
    except Exception as e:
        logger.error(f"Error processing SMS: {str(e)}")
        raise

async def add_message_to_conversation(
    call_id: int,
    message_body: str,
    direction: str,
    provider: str,
    message_sid: str,
    db: Session
):
    """Add message to existing conversation"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        # Parse existing messages
        current_messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        
        # Add new message
        current_messages.append({
            "timestamp": datetime.utcnow().isoformat(),
            "message": message_body,
            "direction": direction,
            "provider": provider,
            "message_sid": message_sid
        })
        
        # Update call record
        call_record.text_messages = json.dumps(current_messages)
        call_record.mobile_texts_count = (call_record.mobile_texts_count or 0) + 1
        call_record.updated_at = datetime.utcnow()
        
        db.commit()
        logger.info(f"Message added to conversation {call_id}")
        
    except Exception as e:
        logger.error(f"Error adding message to conversation: {str(e)}")
        raise

async def send_auto_reply_if_needed(
    call_id: int,
    from_number: str,
    company_record: company.Company,
    db: Session
) -> bool:
    """Send auto-reply if this is the first message in conversation"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            return False
        
        # Check if this is the first inbound message
        messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        inbound_messages = [msg for msg in messages if msg.get("direction") == "inbound"]
        
        if len(inbound_messages) == 1:  # First inbound message
            return await send_welcome_message(
                to_number=from_number,
                company_record=company_record,
                call_id=call_id,
                db=db
            )
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking auto-reply: {str(e)}")
        return False

async def send_welcome_message(
    to_number: str,
    company_record: company.Company,
    call_id: int,
    db: Session
) -> bool:
    """Send welcome message to new SMS lead"""
    try:
        # Create welcome message
        welcome_message = (
            f"Hi! Thanks for reaching out to {company_record.name}.\n\n"
            "We received your message and will get back to you shortly.\n\n"
            "In the meantime, you can:\n"
            "- Reply with your address for a quick quote\n"
            "- Let us know your preferred appointment time\n"
            "- Ask any questions about our services\n\n"
            "We're here to help!"
        )
        
        # Send SMS via Twilio
        sms_result = await twilio_service.send_sms(
            to=to_number,
            body=welcome_message,
            from_number=company_record.phone_number
        )
        
        if sms_result.get("status") == "success":
            # Add outbound message to conversation
            await add_message_to_conversation(
                call_id=call_id,
                message_body=welcome_message,
                direction="outbound",
                provider="twilio",
                message_sid=sms_result.get("message_sid", ""),
                db=db
            )
            
            logger.info(f"Welcome message sent to {to_number}")
            return True
        else:
            logger.error(f"Failed to send welcome message: {sms_result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending welcome message: {str(e)}")
        return False

@router.get("/conversations/{call_id}")
async def get_sms_conversation(
    call_id: int,
    db: Session = Depends(get_db)
):
    """Get SMS conversation history"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        messages = json.loads(call_record.text_messages) if call_record.text_messages else []
        
        return {
            "call_id": call_id,
            "phone_number": call_record.phone_number,
            "company_id": call_record.company_id,
            "total_messages": len(messages),
            "messages": messages
        }
        
    except Exception as e:
        logger.error(f"Error getting SMS conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send")
async def send_sms_to_customer(
    call_id: int,
    message: str,
    db: Session = Depends(get_db)
):
    """Send SMS to customer"""
    try:
        call_record = db.query(call.Call).filter_by(call_id=call_id).first()
        if not call_record:
            raise HTTPException(status_code=404, detail="Call not found")
        
        company_record = db.query(company.Company).filter_by(id=call_record.company_id).first()
        if not company_record:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check if human has taken over and stop AI automation
        from app.services.missed_call_queue_service import MissedCallQueueService
        missed_call_service = MissedCallQueueService()
        
        # This human SMS will trigger takeover detection
        await missed_call_service.check_and_stop_ai_automation(
            phone=call_record.phone_number,
            db=db
        )
        
        # Send SMS
        sms_result = await twilio_service.send_sms(
            to=call_record.phone_number,
            body=message,
            from_number=company_record.phone_number
        )
        
        if sms_result.get("status") == "success":
            # Add to conversation with human marker
            await add_message_to_conversation(
                call_id=call_id,
                message_body=message,
                direction="outbound",
                provider="twilio",
                message_sid=sms_result.get("message_sid", ""),
                db=db
            )
            
            # Mark this as human-generated message to prevent AI takeover detection
            call_record = db.query(call.Call).filter_by(call_id=call_id).first()
            if call_record:
                messages = json.loads(call_record.text_messages) if call_record.text_messages else []
                if messages:
                    messages[-1]["human_generated"] = True
                    call_record.text_messages = json.dumps(messages)
                    db.commit()
            
            return {"status": "sent", "message_sid": sms_result.get("message_sid")}
        else:
            raise HTTPException(status_code=500, detail=f"SMS send failed: {sms_result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
