"""
Background Queue Processor
Continuously processes the missed call queue with SLA management
"""
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.missed_call_queue_service import MissedCallQueueService
from app.obs.logging import get_logger

logger = get_logger(__name__)

class QueueProcessor:
    """Background processor for missed call queue"""
    
    def __init__(self):
        self.service = MissedCallQueueService()
        self.running = False
        self.processing_interval = 60  # Process every 60 seconds
        self.sla_check_interval = 300  # Check SLA every 5 minutes
    
    async def start(self):
        """Start the background queue processor"""
        if self.running:
            logger.warning("Queue processor is already running")
            return
        
        self.running = True
        logger.info("Starting missed call queue processor")
        
        # Start processing tasks
        asyncio.create_task(self._process_queue_loop())
        asyncio.create_task(self._sla_monitor_loop())
        
    async def stop(self):
        """Stop the background queue processor"""
        self.running = False
        logger.info("Stopping missed call queue processor")
    
    async def _process_queue_loop(self):
        """Main queue processing loop"""
        while self.running:
            try:
                db = SessionLocal()
                try:
                    stats = await self.service.process_queue(db)
                    if stats["processed"] > 0:
                        logger.info(f"Queue processing completed: {stats}")
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error in queue processing loop: {str(e)}")
            
            # Wait before next processing cycle
            await asyncio.sleep(self.processing_interval)
    
    async def _sla_monitor_loop(self):
        """SLA monitoring loop"""
        while self.running:
            try:
                db = SessionLocal()
                try:
                    await self.service._check_expired_items(db)
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error in SLA monitoring loop: {str(e)}")
            
            # Wait before next SLA check
            await asyncio.sleep(self.sla_check_interval)
    
    async def process_single_queue_entry(self, queue_id: int) -> bool:
        """Process a single queue entry immediately"""
        try:
            db = SessionLocal()
            try:
                from app.models.missed_call_queue import MissedCallQueue
                
                queue_entry = db.query(MissedCallQueue).filter_by(id=queue_id).first()
                if not queue_entry:
                    logger.error(f"Queue entry not found: {queue_id}")
                    return False
                
                result = await self.service._process_missed_call(queue_entry, db)
                logger.info(f"Processed queue entry {queue_id}: {result}")
                return result in ["recovered", "escalated"]
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error processing single queue entry {queue_id}: {str(e)}")
            return False
    
    async def get_processor_status(self) -> dict:
        """Get processor status and statistics"""
        try:
            db = SessionLocal()
            try:
                from app.models.missed_call_queue import MissedCallQueue, MissedCallStatus
                
                # Get overall queue statistics
                total_queued = db.query(MissedCallQueue).filter(
                    MissedCallQueue.status == MissedCallStatus.QUEUED
                ).count()
                
                total_processing = db.query(MissedCallQueue).filter(
                    MissedCallQueue.status == MissedCallStatus.PROCESSING
                ).count()
                
                total_pending = db.query(MissedCallQueue).filter(
                    MissedCallQueue.status == MissedCallStatus.AI_RESCUED_PENDING
                ).count()
                
                # Get SLA violations
                now = datetime.utcnow()
                sla_violations = db.query(MissedCallQueue).filter(
                    MissedCallQueue.status.in_([
                        MissedCallStatus.QUEUED,
                        MissedCallStatus.PROCESSING
                    ]),
                    MissedCallQueue.sla_deadline < now
                ).count()
                
                return {
                    "running": self.running,
                    "processing_interval": self.processing_interval,
                    "sla_check_interval": self.sla_check_interval,
                    "queue_stats": {
                        "queued": total_queued,
                        "processing": total_processing,
                        "pending_response": total_pending,
                        "sla_violations": sla_violations
                    }
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error getting processor status: {str(e)}")
            return {"error": str(e)}

# Global processor instance
queue_processor = QueueProcessor()















