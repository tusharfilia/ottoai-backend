"""
Missed Call Queue Service
Implements systematic processing of missed calls with SLA management and AI-led recovery
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from app.models.missed_call_queue import (
    MissedCallQueue, 
    MissedCallAttempt, 
    MissedCallSLA,
    MissedCallStatus, 
    MissedCallPriority
)
from app.models import call, company
from app.services.twilio_service import TwilioService
from app.services.uwc_client import get_uwc_client
from app.services.redis_lock_service import redis_lock_service
from app.realtime.bus import emit
from app.obs.logging import get_logger
import json
import hashlib
import hmac

logger = get_logger(__name__)

class MissedCallQueueService:
    """Service for managing missed call queue and AI-led recovery with distributed locking"""
    
    def __init__(self):
        self.twilio_service = TwilioService()
        self.uwc_client = None
        self.lock_service = redis_lock_service
        
    def get_uwc_client(self):
        """Get UWC client lazily"""
        if self.uwc_client is None:
            self.uwc_client = get_uwc_client()
        return self.uwc_client
    
    async def add_missed_call_to_queue(
        self, 
        call_id: int, 
        customer_phone: str, 
        company_id: str, 
        db: Session
    ) -> MissedCallQueue:
        """
        Add a missed call to the queue for systematic processing
        
        Args:
            call_id: ID of the missed call
            customer_phone: Customer's phone number
            company_id: Company ID
            db: Database session
            
        Returns:
            MissedCallQueue entry
        """
        try:
            # Get company SLA settings
            sla_settings = db.query(MissedCallSLA).filter_by(company_id=company_id).first()
            if not sla_settings:
                # Create default SLA settings
                sla_settings = MissedCallSLA(
                    company_id=company_id,
                    response_time_hours=2,
                    escalation_time_hours=48,
                    max_retries=3
                )
                db.add(sla_settings)
                db.commit()
            
            # Determine customer type and priority
            customer_type, priority = await self._analyze_customer(customer_phone, company_id, db)
            
            # Calculate SLA deadlines
            now = datetime.utcnow()
            sla_deadline = now + timedelta(hours=sla_settings.response_time_hours)
            escalation_deadline = now + timedelta(hours=sla_settings.escalation_time_hours)
            
            # Create queue entry
            queue_entry = MissedCallQueue(
                call_id=call_id,
                customer_phone=customer_phone,
                company_id=company_id,
                status=MissedCallStatus.QUEUED,
                priority=priority,
                sla_deadline=sla_deadline,
                escalation_deadline=escalation_deadline,
                max_retries=sla_settings.max_retries,
                customer_type=customer_type,
                conversation_context=json.dumps({
                    "initial_missed_call": True,
                    "customer_type": customer_type,
                    "priority": priority.value
                })
            )
            
            db.add(queue_entry)
            db.commit()
            db.refresh(queue_entry)
            
            logger.info(f"Added missed call to queue: {queue_entry.id}")
            
            # Immediately process the first SMS attempt (don't wait for queue processor)
            try:
                result = await self._process_missed_call(queue_entry, db)
                logger.info(f"Immediate SMS processing result for queue entry {queue_entry.id}: {result}")
            except Exception as e:
                logger.error(f"Failed to send immediate SMS for queue entry {queue_entry.id}: {str(e)}")
                # Don't fail the whole operation if SMS fails - queue will retry later
            
            # Emit real-time event
            emit(
                event_name="missed_call.queued",
                payload={
                    "queue_id": queue_entry.id,
                    "call_id": call_id,
                    "customer_phone": customer_phone,
                    "priority": priority.value,
                    "sla_deadline": sla_deadline.isoformat()
                },
                tenant_id=company_id,
                lead_id=call_id
            )
            
            return queue_entry
            
        except Exception as e:
            logger.error(f"Error adding missed call to queue: {str(e)}")
            raise
    
    async def process_queue(self, db: Session) -> Dict[str, int]:
        """
        Process the missed call queue
        
        Returns:
            Dict with processing statistics
        """
        stats = {
            "processed": 0,
            "recovered": 0,
            "escalated": 0,
            "failed": 0
        }
        
        try:
            # Get queued items that need processing (immediate or retry)
            now = datetime.utcnow()
            queued_items = db.query(MissedCallQueue).filter(
                or_(
                    # New items in queue
                    and_(
                        MissedCallQueue.status == MissedCallStatus.QUEUED,
                        MissedCallQueue.sla_deadline > now,  # Not expired
                        MissedCallQueue.customer_responded == False  # Customer hasn't responded yet
                    ),
                    # Items ready for retry (but only if customer hasn't responded)
                    and_(
                        MissedCallQueue.status == MissedCallStatus.AI_RESCUED_PENDING,
                        MissedCallQueue.next_attempt_at <= now,  # Ready for retry
                        MissedCallQueue.retry_count < MissedCallQueue.max_retries,  # Haven't exceeded max retries
                        MissedCallQueue.customer_responded == False  # Customer hasn't responded yet
                    )
                )
            ).order_by(
                desc(MissedCallQueue.priority),  # High priority first
                asc(MissedCallQueue.created_at)  # FIFO within priority
            ).limit(10).all()  # Process in batches
            
            for queue_entry in queued_items:
                try:
                    result = await self._process_missed_call(queue_entry, db)
                    stats["processed"] += 1
                    
                    if result == "recovered":
                        stats["recovered"] += 1
                    elif result == "escalated":
                        stats["escalated"] += 1
                    elif result == "failed":
                        stats["failed"] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing queue entry {queue_entry.id}: {str(e)}")
                    queue_entry.status = MissedCallStatus.FAILED
                    db.commit()
                    stats["failed"] += 1
            
            # Check for expired items
            await self._check_expired_items(db)
            
            logger.info(f"Queue processing completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error processing missed call queue: {str(e)}")
            raise
    
    async def _process_missed_call(self, queue_entry: MissedCallQueue, db: Session) -> str:
        """Process a single missed call entry with distributed locking"""
        lock_key = f"missed_call_queue:{queue_entry.id}"
        lock_token = None
        
        try:
            # Acquire distributed lock to prevent race conditions
            lock_token = await self.lock_service.acquire_lock(
                lock_key=lock_key,
                tenant_id=queue_entry.company_id,
                timeout=300  # 5 minutes
            )
            
            if not lock_token:
                logger.warning(f"Could not acquire lock for queue entry {queue_entry.id}")
                return "failed"
            
            # Refresh from database to get latest state (in case customer responded while waiting for lock)
            db.refresh(queue_entry)
            
            # Check if customer has already responded (shouldn't happen, but double-check for safety)
            if queue_entry.customer_responded or queue_entry.status == MissedCallStatus.RECOVERED:
                logger.info(f"Customer already responded for queue entry {queue_entry.id}, skipping follow-up SMS")
                return "recovered"
            
            # Check if human has taken over (CSR called back)
            if await self._check_human_takeover(queue_entry, db):
                logger.info(f"Human takeover detected for queue entry {queue_entry.id}, stopping AI automation")
                queue_entry.status = MissedCallStatus.ESCALATED
                queue_entry.escalated_at = datetime.utcnow()
                db.commit()
                return "escalated"
            
            # Update status to processing
            queue_entry.status = MissedCallStatus.PROCESSING
            queue_entry.last_attempt_at = datetime.utcnow()
            db.commit()
            
            # Get company info
            company_record = db.query(company.Company).filter_by(id=queue_entry.company_id).first()
            if not company_record:
                logger.error(f"Company not found: {queue_entry.company_id}")
                return "failed"
            
            # Generate AI-led SMS based on customer type and retry count
            sms_content = await self._generate_ai_sms(
                queue_entry.customer_type,
                company_record.name,
                queue_entry.conversation_context,
                queue_entry.retry_count
            )
            
            # Send SMS via Twilio
            # Use default TWILIO_FROM_NUMBER (don't use company phone which is CallRail tracking number)
            sms_result = await self.twilio_service.send_sms(
                to=queue_entry.customer_phone,
                body=sms_content,
                from_number=None  # Will use TWILIO_FROM_NUMBER from environment
            )
            
            if sms_result.get("status") == "success":
                # Record attempt
                attempt = MissedCallAttempt(
                    queue_id=queue_entry.id,
                    attempt_number=queue_entry.retry_count + 1,
                    method="sms",
                    message_sent=sms_content,
                    attempted_at=datetime.utcnow()
                )
                db.add(attempt)
                
                # Update queue entry with new retry schedule
                queue_entry.retry_count += 1
                queue_entry.ai_rescue_attempted = True
                queue_entry.status = MissedCallStatus.AI_RESCUED_PENDING
                
                # Set next attempt based on retry count
                next_attempt_time = self._calculate_next_attempt(queue_entry.retry_count)
                queue_entry.next_attempt_at = next_attempt_time
                
                db.commit()
                
                logger.info(f"AI rescue SMS sent for queue entry {queue_entry.id} (attempt {queue_entry.retry_count})")
                return "recovered"
            else:
                logger.error(f"Failed to send SMS: {sms_result.get('error')}")
                return "failed"
                
        except Exception as e:
            logger.error(f"Error processing missed call {queue_entry.id}: {str(e)}")
            return "failed"
        finally:
            # Always release the lock
            if lock_token:
                await self.lock_service.release_lock(
                    lock_key=lock_key,
                    tenant_id=queue_entry.company_id,
                    lock_token=lock_token
                )
    
    async def _check_human_takeover(self, queue_entry: MissedCallQueue, db: Session) -> bool:
        """Check if human CSR has taken over the conversation (call or text)"""
        try:
            # Check if there's been a recent call from CSR to this customer
            recent_call = db.query(call.Call).filter(
                call.Call.phone_number == queue_entry.customer_phone,
                call.Call.company_id == queue_entry.company_id,
                call.Call.created_at > queue_entry.created_at,  # After the missed call
                call.Call.missed_call == False  # Call was answered
            ).first()
            
            if recent_call:
                logger.info(f"Human takeover detected: CSR called {queue_entry.customer_phone} after missed call")
                return True
            
            # Check if there's been manual escalation
            if queue_entry.status == MissedCallStatus.ESCALATED:
                return True
            
            # Check if human CSR has sent SMS to this customer
            if await self._check_human_sms_takeover(queue_entry, db):
                logger.info(f"Human takeover detected: CSR sent SMS to {queue_entry.customer_phone}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking human takeover: {str(e)}")
            return False
    
    async def _check_human_sms_takeover(self, queue_entry: MissedCallQueue, db: Session) -> bool:
        """Check if human CSR has sent SMS to this customer"""
        try:
            # Get the call record for this queue entry
            call_record = db.query(call.Call).filter_by(call_id=queue_entry.call_id).first()
            if not call_record:
                return False
            
            # Parse SMS messages from the call record
            messages = json.loads(call_record.text_messages) if call_record.text_messages else []
            
            # Check for outbound messages sent after the queue entry was created
            for message in messages:
                if (message.get("direction") == "outbound" and 
                    message.get("timestamp") and 
                    datetime.fromisoformat(message["timestamp"].replace('Z', '+00:00')) > queue_entry.created_at):
                    
                    # Check if this message was sent by a human (not AI)
                    # AI messages have specific patterns or are sent via background tasks
                    # Human messages are sent via the API endpoints
                    if not self._is_ai_generated_message(message):
                        logger.info(f"Human SMS detected: {message.get('message', '')[:50]}...")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking human SMS takeover: {str(e)}")
            return False
    
    def _is_ai_generated_message(self, message: dict) -> bool:
        """Check if a message was generated by AI automation"""
        try:
            # Check if message is explicitly marked as human-generated
            if message.get("human_generated"):
                return False
            
            message_text = message.get("message", "").lower()
            
            # AI-generated messages have specific patterns
            ai_patterns = [
                "we just missed your call",
                "we're still here to help",
                "we don't want you to miss out",
                "last chance for your free quote",
                "thanks for reaching out",
                "we received your message"
            ]
            
            # Check if message contains AI patterns
            for pattern in ai_patterns:
                if pattern in message_text:
                    return True
            
            # Check if message was sent by background task (AI)
            if message.get("provider") == "ai_automation":
                return True
            
            # Check if message was sent by missed call queue system
            if message.get("provider") == "missed_call_queue":
                return True
            
            # If message doesn't match AI patterns and isn't marked as human, assume it's human-generated
            return False
            
        except Exception as e:
            logger.error(f"Error checking if message is AI-generated: {str(e)}")
            return False
    
    def _calculate_next_attempt(self, retry_count: int) -> datetime:
        """Calculate next attempt time based on retry schedule"""
        now = datetime.utcnow()
        
        if retry_count == 1:
            # First retry: 2 hours
            return now + timedelta(hours=2)
        elif retry_count == 2:
            # Second retry: 10 hours
            return now + timedelta(hours=10)
        elif retry_count == 3:
            # Third retry: 24 hours
            return now + timedelta(hours=24)
        else:
            # After 3 attempts, escalate to human
            return now + timedelta(hours=24)
    
    async def _generate_ai_sms(
        self, 
        customer_type: str, 
        company_name: str, 
        context: str,
        retry_count: int = 0
    ) -> str:
        """Generate AI-led SMS content based on customer type, context, and retry count"""
        try:
            # Parse context
            context_data = json.loads(context) if context else {}
            
            # Different messages based on retry count
            if retry_count == 0:
                # Initial message - immediate response
                if customer_type == "new":
                    message = f"""Hi! We just missed your call to {company_name}. 

We'd love to help you with your project! 

Reply with:
• Your address for a quick quote
• Your preferred time to talk
• Any questions you have

We'll get back to you within 2 hours! 🏠"""
                else:  # existing customer
                    message = f"""Hi! We just missed your call to {company_name}. 

Thanks for reaching out again! 

Reply with:
• Your address for a quick quote
• Your preferred time to talk
• Any questions you have

We'll get back to you within 2 hours! 🏠"""
            
            elif retry_count == 1:
                # First retry (2 hours later)
                message = f"""Hi! We're still here to help with your {company_name} project. 

Just reply with your address and we'll send you a quick quote! 

No pressure - we're here when you're ready. 🏠"""
            
            elif retry_count == 2:
                # Second retry (10 hours later)
                message = f"""Hi! We don't want you to miss out on your {company_name} project. 

We have availability this week and can provide a free quote. 

Just reply with your address - takes 30 seconds! 🏠"""
            
            elif retry_count == 3:
                # Third retry (24 hours later) - final attempt
                message = f"""Hi! Last chance for your free {company_name} quote. 

We're here to help - just reply with your address. 

If you're not interested, just reply "STOP" and we'll remove you from our list. 🏠"""
            
            else:
                # Fallback
                message = f"Hi! We're here to help with your {company_name} project. Reply with your address for a free quote! 🏠"
            
            # TODO: Integrate with UWC for dynamic AI-generated responses
            # For now, using template-based approach with retry logic
            
            return message
            
        except Exception as e:
            logger.error(f"Error generating AI SMS: {str(e)}")
            # Fallback to simple message
            return f"Hi! We missed your call to {company_name}. How can we help you today? Reply with your name and we'll get back to you shortly."
    
    async def _analyze_customer(self, phone: str, company_id: str, db: Session) -> Tuple[str, MissedCallPriority]:
        """Analyze customer to determine type and priority"""
        try:
            # Check if customer has previous calls
            previous_calls = db.query(call.Call).filter_by(
                phone_number=phone,
                company_id=company_id
            ).count()
            
            if previous_calls <= 1:
                customer_type = "new"
                priority = MissedCallPriority.HIGH
            else:
                customer_type = "existing"
                priority = MissedCallPriority.MEDIUM
            
            return customer_type, priority
            
        except Exception as e:
            logger.error(f"Error analyzing customer: {str(e)}")
            return "unknown", MissedCallPriority.MEDIUM
    
    async def _check_expired_items(self, db: Session):
        """Check for items that have exceeded SLA deadlines"""
        try:
            now = datetime.utcnow()
            
            # Find expired items
            expired_items = db.query(MissedCallQueue).filter(
                MissedCallQueue.status.in_([
                    MissedCallStatus.QUEUED,
                    MissedCallStatus.PROCESSING,
                    MissedCallStatus.AI_RESCUED_PENDING
                ]),
                MissedCallQueue.escalation_deadline < now
            ).all()
            
            for item in expired_items:
                # Escalate to human CSR
                item.status = MissedCallStatus.ESCALATED
                item.escalated_at = now
                db.commit()
                
                logger.info(f"Escalated expired missed call: {item.id}")
                
                # Emit escalation event
                emit(
                    event_name="missed_call.escalated",
                    payload={
                        "queue_id": item.id,
                        "call_id": item.call_id,
                        "customer_phone": item.customer_phone,
                        "reason": "sla_expired"
                    },
                    tenant_id=item.company_id,
                    lead_id=item.call_id
                )
                
        except Exception as e:
            logger.error(f"Error checking expired items: {str(e)}")
    
    async def handle_customer_response(
        self, 
        phone: str, 
        response_text: str, 
        db: Session
    ) -> Optional[MissedCallQueue]:
        """Handle customer response to AI-led SMS"""
        try:
            # Check for STOP command
            if response_text.upper().strip() == "STOP":
                return await self._handle_stop_request(phone, db)
            
            # Find active queue entry for this phone (any status except RECOVERED, ESCALATED, or FAILED)
            queue_entry = db.query(MissedCallQueue).filter(
                MissedCallQueue.customer_phone == phone,
                MissedCallQueue.status.in_([
                    MissedCallStatus.QUEUED,
                    MissedCallStatus.PROCESSING,
                    MissedCallStatus.AI_RESCUED_PENDING
                ])
            ).first()
            
            if not queue_entry:
                logger.warning(f"No active queue entry found for phone: {phone}")
                return None
            
            # Update queue entry
            queue_entry.customer_responded = True
            queue_entry.status = MissedCallStatus.RECOVERED
            queue_entry.processed_at = datetime.utcnow()
            
            # Update conversation context
            context = json.loads(queue_entry.conversation_context) if queue_entry.conversation_context else {}
            context["customer_response"] = response_text
            context["response_received_at"] = datetime.utcnow().isoformat()
            queue_entry.conversation_context = json.dumps(context)
            
            db.commit()
            
            logger.info(f"Customer response processed for queue entry {queue_entry.id}")
            
            # Emit recovery event
            emit(
                event_name="missed_call.recovered",
                payload={
                    "queue_id": queue_entry.id,
                    "call_id": queue_entry.call_id,
                    "customer_phone": phone,
                    "response": response_text
                },
                tenant_id=queue_entry.company_id,
                lead_id=queue_entry.call_id
            )
            
            return queue_entry
            
        except Exception as e:
            logger.error(f"Error handling customer response: {str(e)}")
            return None
    
    async def _handle_stop_request(self, phone: str, db: Session) -> Optional[MissedCallQueue]:
        """Handle STOP request from customer"""
        try:
            # Find active queue entry
            queue_entry = db.query(MissedCallQueue).filter(
                MissedCallQueue.customer_phone == phone,
                MissedCallQueue.status.in_([
                    MissedCallStatus.QUEUED,
                    MissedCallStatus.PROCESSING,
                    MissedCallStatus.AI_RESCUED_PENDING
                ])
            ).first()
            
            if queue_entry:
                # Mark as stopped
                queue_entry.status = MissedCallStatus.FAILED
                queue_entry.processed_at = datetime.utcnow()
                
                # Update context
                context = json.loads(queue_entry.conversation_context) if queue_entry.conversation_context else {}
                context["customer_stopped"] = True
                context["stop_requested_at"] = datetime.utcnow().isoformat()
                queue_entry.conversation_context = json.dumps(context)
                
                db.commit()
                
                logger.info(f"Customer STOP request processed for queue entry {queue_entry.id}")
                
                # Emit stop event
                emit(
                    event_name="missed_call.stopped",
                    payload={
                        "queue_id": queue_entry.id,
                        "call_id": queue_entry.call_id,
                        "customer_phone": phone,
                        "reason": "customer_stop_request"
                    },
                    tenant_id=queue_entry.company_id,
                    lead_id=queue_entry.call_id
                )
                
                return queue_entry
            
            return None
            
        except Exception as e:
            logger.error(f"Error handling STOP request: {str(e)}")
            return None
    
    async def get_queue_status(self, company_id: str, db: Session) -> Dict[str, int]:
        """Get queue status for a company"""
        try:
            status_counts = {}
            
            for status in MissedCallStatus:
                count = db.query(MissedCallQueue).filter(
                    MissedCallQueue.company_id == company_id,
                    MissedCallQueue.status == status
                ).count()
                status_counts[status.value] = count
            
            return status_counts
            
        except Exception as e:
            logger.error(f"Error getting queue status: {str(e)}")
            return {}
    
    async def get_queue_metrics(self, company_id: str, db: Session, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, float]:
        """Get queue performance metrics"""
        try:
            from datetime import datetime as dt
            
            # Build base query with company filter
            base_filter = [MissedCallQueue.company_id == company_id]
            
            # Add date filters if provided
            if start_date:
                try:
                    # Handle both ISO format (with T) and YYYY-MM-DD format
                    if 'T' in start_date:
                        start_dt = dt.fromisoformat(start_date.replace('Z', '+00:00'))
                    else:
                        start_dt = dt.strptime(start_date, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
                    base_filter.append(MissedCallQueue.created_at >= start_dt)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Invalid start_date format: {start_date}, error: {str(e)}")
            
            if end_date:
                try:
                    # Handle both ISO format (with T) and YYYY-MM-DD format
                    if 'T' in end_date:
                        end_dt = dt.fromisoformat(end_date.replace('Z', '+00:00'))
                    else:
                        end_dt = dt.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                    base_filter.append(MissedCallQueue.created_at <= end_dt)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Invalid end_date format: {end_date}, error: {str(e)}")
            
            # Recovery rate
            total_processed = db.query(MissedCallQueue).filter(
                *base_filter,
                MissedCallQueue.status.in_([
                    MissedCallStatus.RECOVERED,
                    MissedCallStatus.ESCALATED,
                    MissedCallStatus.FAILED
                ])
            ).count()
            
            recovered_count = db.query(MissedCallQueue).filter(
                *base_filter,
                MissedCallQueue.status == MissedCallStatus.RECOVERED
            ).count()
            
            recovery_rate = (recovered_count / total_processed * 100) if total_processed > 0 else 0
            
            # Average response time
            avg_response_time = db.query(
                func.avg(
                    func.extract('epoch', MissedCallQueue.processed_at - MissedCallQueue.created_at)
                )
            ).filter(
                *base_filter,
                MissedCallQueue.status == MissedCallStatus.RECOVERED
            ).scalar() or 0
            
            return {
                "recovery_rate": recovery_rate,
                "avg_response_time_hours": avg_response_time / 3600,
                "total_processed": total_processed,
                "recovered_count": recovered_count
            }
            
        except Exception as e:
            logger.error(f"Error getting queue metrics: {str(e)}")
            return {}
    
    async def check_and_stop_ai_automation(self, phone: str, db: Session) -> bool:
        """
        Check if human has taken over conversation and stop AI automation
        
        This method is called whenever a customer sends an SMS to detect if
        a human CSR has taken over the conversation and stop AI automation.
        """
        try:
            # Find active queue entries for this phone
            active_entries = db.query(MissedCallQueue).filter(
                MissedCallQueue.customer_phone == phone,
                MissedCallQueue.status.in_([
                    MissedCallStatus.QUEUED,
                    MissedCallStatus.PROCESSING,
                    MissedCallStatus.AI_RESCUED_PENDING
                ])
            ).all()
            
            if not active_entries:
                return False
            
            # Check each active entry for human takeover
            human_takeover_detected = False
            for entry in active_entries:
                if await self._check_human_takeover(entry, db):
                    # Stop AI automation for this entry
                    entry.status = MissedCallStatus.ESCALATED
                    entry.escalated_at = datetime.utcnow()
                    
                    # Update context
                    context = json.loads(entry.conversation_context) if entry.conversation_context else {}
                    context["human_takeover_detected"] = True
                    context["takeover_detected_at"] = datetime.utcnow().isoformat()
                    context["takeover_reason"] = "human_intervention"
                    entry.conversation_context = json.dumps(context)
                    
                    human_takeover_detected = True
                    
                    logger.info(f"Human takeover detected for queue entry {entry.id}, stopping AI automation")
                    
                    # Emit takeover event
                    emit(
                        event_name="missed_call.human_takeover",
                        payload={
                            "queue_id": entry.id,
                            "call_id": entry.call_id,
                            "customer_phone": phone,
                            "reason": "human_intervention"
                        },
                        tenant_id=entry.company_id,
                        lead_id=entry.call_id
                    )
            
            if human_takeover_detected:
                db.commit()
                logger.info(f"AI automation stopped for {len(active_entries)} queue entries due to human takeover")
            
            return human_takeover_detected
            
        except Exception as e:
            logger.error(f"Error checking and stopping AI automation: {str(e)}")
            return False
