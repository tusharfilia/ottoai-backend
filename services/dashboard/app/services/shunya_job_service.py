"""
Shunya Job Service for managing async Shunya API jobs.

Handles job creation, status tracking, retry logic, and idempotency.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.shunya_job import ShunyaJob, ShunyaJobType, ShunyaJobStatus
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class ShunyaJobService:
    """
    Service for managing Shunya async jobs.
    
    Responsibilities:
    - Create and track jobs
    - Handle job status transitions
    - Manage retries with exponential backoff
    - Ensure idempotency
    """
    
    # Maximum retry delays (seconds)
    MAX_RETRY_DELAY = 300  # 5 minutes
    INITIAL_RETRY_DELAY = 5
    RETRY_MULTIPLIER = 2
    
    # Job timeout (from creation)
    JOB_TIMEOUT_HOURS = 24
    
    def create_job(
        self,
        db: Session,
        company_id: str,
        job_type: ShunyaJobType,
        input_payload: Dict[str, Any],
        contact_card_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        call_id: Optional[int] = None,
        recording_session_id: Optional[str] = None,
    ) -> ShunyaJob:
        """
        Create a new Shunya job.
        
        Args:
            db: Database session
            company_id: Company/tenant ID
            job_type: Type of job (csr_call, sales_visit, segmentation)
            input_payload: Input data sent to Shunya
            contact_card_id: Optional contact card ID
            lead_id: Optional lead ID
            appointment_id: Optional appointment ID
            call_id: Optional call ID (integer)
            recording_session_id: Optional recording session ID
        
        Returns:
            Created ShunyaJob instance
        """
        job = ShunyaJob(
            company_id=company_id,
            job_type=job_type,
            job_status=ShunyaJobStatus.PENDING,
            input_payload=input_payload,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            appointment_id=appointment_id,
            call_id=call_id,
            recording_session_id=recording_session_id,
            num_attempts=0,
            max_attempts=5,
        )
        db.add(job)
        db.flush()
        db.refresh(job)
        
        logger.info(
            f"Created Shunya job {job.id}",
            extra={
                "job_id": job.id,
                "job_type": job_type.value,
                "company_id": company_id,
            }
        )
        
        return job
    
    def mark_running(
        self,
        db: Session,
        job: ShunyaJob,
        shunya_job_id: Optional[str] = None,
    ) -> ShunyaJob:
        """
        Mark job as running.
        
        Args:
            db: Database session
            job: ShunyaJob instance
            shunya_job_id: Shunya's job ID (if available)
        
        Returns:
            Updated ShunyaJob instance
        """
        job.job_status = ShunyaJobStatus.RUNNING
        job.started_at = datetime.utcnow()
        
        if shunya_job_id:
            job.shunya_job_id = shunya_job_id
        
        job.num_attempts += 1
        job.last_attempt_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(job)
        
        logger.info(
            f"Marked Shunya job {job.id} as running",
            extra={
                "job_id": job.id,
                "shunya_job_id": shunya_job_id,
            }
        )
        
        return job
    
    def mark_succeeded(
        self,
        db: Session,
        job: ShunyaJob,
        output_payload: Dict[str, Any],
    ) -> ShunyaJob:
        """
        Mark job as succeeded and store normalized output.
        
        Args:
            db: Database session
            job: ShunyaJob instance
            output_payload: Normalized Shunya output
        
        Returns:
            Updated ShunyaJob instance
        """
        from app.utils.idempotency import generate_output_payload_hash
        
        # Check idempotency: don't update if already succeeded with same output
        output_hash = generate_output_payload_hash(output_payload)
        if (
            job.job_status == ShunyaJobStatus.SUCCEEDED
            and job.processed_output_hash == output_hash
        ):
            logger.warning(
                f"Shunya job {job.id} already succeeded with same output hash, skipping update",
                extra={"job_id": job.id, "hash": output_hash[:8]}
            )
            return job
        
        job.job_status = ShunyaJobStatus.SUCCEEDED
        job.output_payload = output_payload
        job.processed_output_hash = output_hash  # Store hash for idempotency
        job.completed_at = datetime.utcnow()
        job.next_retry_at = None
        job.error_message = None
        job.error_details = None
        job.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(job)
        
        logger.info(
            f"Marked Shunya job {job.id} as succeeded",
            extra={
                "job_id": job.id,
                "job_type": job.job_type.value,
                "output_hash": output_hash[:8],
            }
        )
        
        return job
    
    def mark_failed(
        self,
        db: Session,
        job: ShunyaJob,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        should_retry: bool = True,
    ) -> ShunyaJob:
        """
        Mark job as failed.
        
        Args:
            db: Database session
            job: ShunyaJob instance
            error_message: Error message
            error_details: Optional error details
            should_retry: Whether to schedule a retry
        
        Returns:
            Updated ShunyaJob instance
        """
        # Check if we should retry
        if should_retry and self.should_retry(job):
            # Schedule retry
            retry_delay = self.next_retry_delay(job)
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=retry_delay)
            job.job_status = ShunyaJobStatus.PENDING  # Move back to pending for retry
            
            logger.info(
                f"Scheduled retry for Shunya job {job.id} in {retry_delay}s",
                extra={
                    "job_id": job.id,
                    "retry_delay": retry_delay,
                    "num_attempts": job.num_attempts,
                }
            )
        else:
            # Mark as failed permanently
            job.job_status = ShunyaJobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.next_retry_at = None
            
            logger.error(
                f"Marked Shunya job {job.id} as failed (no more retries)",
                extra={
                    "job_id": job.id,
                    "error": error_message,
                    "num_attempts": job.num_attempts,
                }
            )
        
        job.error_message = error_message
        job.error_details = error_details
        job.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(job)
        
        return job
    
    def mark_timeout(
        self,
        db: Session,
        job: ShunyaJob,
    ) -> ShunyaJob:
        """
        Mark job as timed out.
        
        Args:
            db: Database session
            job: ShunyaJob instance
        
        Returns:
            Updated ShunyaJob instance
        """
        job.job_status = ShunyaJobStatus.TIMEOUT
        job.completed_at = datetime.utcnow()
        job.error_message = "Job timed out"
        job.next_retry_at = None
        job.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(job)
        
        logger.warning(
            f"Marked Shunya job {job.id} as timed out",
            extra={"job_id": job.id}
        )
        
        return job
    
    def record_attempt(
        self,
        db: Session,
        job: ShunyaJob,
    ) -> ShunyaJob:
        """Record a polling attempt."""
        job.num_attempts += 1
        job.last_attempt_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(job)
        
        return job
    
    def record_result(
        self,
        db: Session,
        job: ShunyaJob,
        output_payload: Dict[str, Any],
    ) -> ShunyaJob:
        """Record job result (normalized output)."""
        job.output_payload = output_payload
        job.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(job)
        
        return job
    
    def should_retry(self, job: ShunyaJob) -> bool:
        """
        Determine if job should be retried.
        
        Args:
            job: ShunyaJob instance
        
        Returns:
            True if job should be retried, False otherwise
        """
        # Check max attempts
        if job.num_attempts >= job.max_attempts:
            return False
        
        # Check timeout
        if job.created_at:
            age = datetime.utcnow() - job.created_at
            if age > timedelta(hours=self.JOB_TIMEOUT_HOURS):
                return False
        
        # Check if already succeeded/failed permanently
        if job.job_status in [ShunyaJobStatus.SUCCEEDED, ShunyaJobStatus.FAILED, ShunyaJobStatus.TIMEOUT]:
            return False
        
        return True
    
    def next_retry_delay(self, job: ShunyaJob) -> int:
        """
        Calculate next retry delay using exponential backoff.
        
        Args:
            job: ShunyaJob instance
        
        Returns:
            Retry delay in seconds (capped at MAX_RETRY_DELAY)
        """
        # Exponential backoff: 5s, 10s, 30s, 60s, 300s (capped)
        attempt = job.num_attempts
        
        if attempt == 1:
            delay = self.INITIAL_RETRY_DELAY  # 5s
        elif attempt == 2:
            delay = 10  # 10s
        elif attempt == 3:
            delay = 30  # 30s
        elif attempt == 4:
            delay = 60  # 60s
        else:
            delay = self.MAX_RETRY_DELAY  # 300s (5 minutes)
        
        return min(delay, self.MAX_RETRY_DELAY)
    
    def is_idempotent(
        self,
        db: Session,
        job: ShunyaJob,
        shunya_job_id: str,
    ) -> bool:
        """
        Check if this Shunya job ID has already been processed.
        
        Args:
            db: Database session
            job: Current ShunyaJob instance
            shunya_job_id: Shunya's job ID
        
        Returns:
            True if already processed, False otherwise
        """
        # Check if another job with this Shunya job ID exists and succeeded
        existing = db.query(ShunyaJob).filter(
            ShunyaJob.company_id == job.company_id,
            ShunyaJob.shunya_job_id == shunya_job_id,
            ShunyaJob.job_status == ShunyaJobStatus.SUCCEEDED,
            ShunyaJob.id != job.id,  # Exclude current job
        ).first()
        
        if existing:
            logger.warning(
                f"Shunya job ID {shunya_job_id} already processed by job {existing.id}",
                extra={
                    "existing_job_id": existing.id,
                    "current_job_id": job.id,
                    "shunya_job_id": shunya_job_id,
                }
            )
            return True
        
        return False
    
    def get_job_by_shunya_id(
        self,
        db: Session,
        company_id: str,
        shunya_job_id: str,
    ) -> Optional[ShunyaJob]:
        """
        Find a job by Shunya job ID.
        
        Args:
            db: Database session
            company_id: Company/tenant ID
            shunya_job_id: Shunya's job ID
        
        Returns:
            ShunyaJob instance or None
        """
        return db.query(ShunyaJob).filter(
            ShunyaJob.company_id == company_id,
            ShunyaJob.shunya_job_id == shunya_job_id,
        ).first()
    
    def get_pending_jobs(
        self,
        db: Session,
        company_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[ShunyaJob]:
        """
        Get pending jobs that are ready for retry.
        
        Args:
            db: Database session
            company_id: Optional company filter
            limit: Maximum number of jobs to return
        
        Returns:
            List of ShunyaJob instances ready for retry
        """
        query = db.query(ShunyaJob).filter(
            ShunyaJob.job_status == ShunyaJobStatus.PENDING,
            ShunyaJob.next_retry_at <= datetime.utcnow(),
        )
        
        if company_id:
            query = query.filter(ShunyaJob.company_id == company_id)
        
        return query.order_by(ShunyaJob.next_retry_at).limit(limit).all()
    
    def get_timed_out_jobs(
        self,
        db: Session,
        company_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[ShunyaJob]:
        """
        Get jobs that have timed out.
        
        Args:
            db: Database session
            company_id: Optional company filter
            limit: Maximum number of jobs to return
        
        Returns:
            List of timed out ShunyaJob instances
        """
        timeout_threshold = datetime.utcnow() - timedelta(hours=self.JOB_TIMEOUT_HOURS)
        
        query = db.query(ShunyaJob).filter(
            ShunyaJob.job_status.in_([ShunyaJobStatus.PENDING, ShunyaJobStatus.RUNNING]),
            ShunyaJob.created_at < timeout_threshold,
        )
        
        if company_id:
            query = query.filter(ShunyaJob.company_id == company_id)
        
        return query.order_by(ShunyaJob.created_at).limit(limit).all()
    
    def should_process(
        self,
        db: Session,
        job: ShunyaJob,
        output_payload: Dict[str, Any],
    ) -> bool:
        """
        Check if a job should be processed based on idempotency rules.
        
        Args:
            db: Database session
            job: ShunyaJob instance
            output_payload: Normalized Shunya output payload
        
        Returns:
            True if job should be processed, False if already processed
        """
        from app.utils.idempotency import generate_output_payload_hash
        
        # If job already succeeded, check output hash
        if job.job_status == ShunyaJobStatus.SUCCEEDED:
            new_hash = generate_output_payload_hash(output_payload)
            if job.processed_output_hash == new_hash:
                logger.info(
                    f"Job {job.id} already processed with same output hash",
                    extra={"job_id": job.id, "hash": new_hash[:8]}
                )
                return False
        
        # Check if another job with same Shunya job ID already succeeded
        if job.shunya_job_id:
            existing = self.get_job_by_shunya_id(db, job.company_id, job.shunya_job_id)
            if existing and existing.id != job.id and existing.job_status == ShunyaJobStatus.SUCCEEDED:
                logger.warning(
                    f"Another job {existing.id} already processed Shunya job ID {job.shunya_job_id}",
                    extra={
                        "current_job_id": job.id,
                        "existing_job_id": existing.id,
                        "shunya_job_id": job.shunya_job_id,
                    }
                )
                return False
        
        return True


# Global service instance
shunya_job_service = ShunyaJobService()

