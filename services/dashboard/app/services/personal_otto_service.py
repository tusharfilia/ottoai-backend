"""
Personal Otto Service for managing AI clone training and profiles.
"""
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.uwc_client import get_uwc_client
from app.models.personal_otto_training_job import PersonalOttoTrainingJob, PersonalOttoTrainingStatus
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class PersonalOttoService:
    """
    Service for managing Personal Otto (AI clone) training and profiles.
    
    Responsibilities:
    - Ingest training documents for sales reps
    - Trigger training jobs
    - Track training status
    - Retrieve Personal Otto profiles
    - Always requires target_role="sales_rep" per Shunya contract
    """
    
    def __init__(self):
        self.uwc_client = get_uwc_client()
        self.target_role = "sales_rep"  # REQUIRED per Shunya contract for Personal Otto
    
    async def ingest_documents_for_rep(
        self,
        db: Session,
        company_id: str,
        rep_id: str,
        documents: List[Dict[str, Any]],
        request_id: str
    ) -> Dict[str, Any]:
        """
        Ingest training documents for a sales rep's Personal Otto.
        
        Args:
            db: Database session
            company_id: Tenant/company ID
            rep_id: Sales rep user ID
            documents: List of training documents
            request_id: Correlation ID
        
        Returns:
            Ingestion response with job_id, status
        """
        try:
            # Call Shunya with REQUIRED target_role="sales_rep"
            result = await self.uwc_client.ingest_personal_otto_documents(
                company_id=company_id,
                request_id=request_id,
                rep_id=rep_id,
                documents=documents,
                target_role=self.target_role  # REQUIRED: Always sales_rep
            )
            
            # Store job tracking if job_id returned
            if result.get("job_id"):
                job = PersonalOttoTrainingJob(
                    id=str(uuid4()),
                    company_id=company_id,
                    rep_id=rep_id,
                    status=PersonalOttoTrainingStatus.PENDING,
                    shunya_job_id=result["job_id"],
                    job_metadata={"ingestion": True, "document_count": len(documents)}
                )
                db.add(job)
                db.commit()
            
            return result
            
        except Exception as e:
            logger.error(
                f"Failed to ingest Personal Otto documents for rep {rep_id}: {str(e)}",
                extra={"rep_id": rep_id, "company_id": company_id},
                exc_info=True
            )
            raise
    
    async def trigger_training_for_rep(
        self,
        db: Session,
        company_id: str,
        rep_id: str,
        request_id: str,
        force_retrain: bool = False
    ) -> Dict[str, Any]:
        """
        Trigger Personal Otto training for a sales rep.
        
        Args:
            db: Database session
            company_id: Tenant/company ID
            rep_id: Sales rep user ID
            request_id: Correlation ID
            force_retrain: If True, force retraining even if already trained
        
        Returns:
            Training response with job_id, status
        """
        try:
            # Call Shunya with REQUIRED target_role="sales_rep"
            result = await self.uwc_client.run_personal_otto_training(
                company_id=company_id,
                request_id=request_id,
                rep_id=rep_id,
                target_role=self.target_role,  # REQUIRED: Always sales_rep
                force_retrain=force_retrain
            )
            
            # Get or create training job record
            job = db.query(PersonalOttoTrainingJob).filter(
                PersonalOttoTrainingJob.company_id == company_id,
                PersonalOttoTrainingJob.rep_id == rep_id
            ).first()
            
            if not job:
                job = PersonalOttoTrainingJob(
                    id=str(uuid4()),
                    company_id=company_id,
                    rep_id=rep_id,
                    status=PersonalOttoTrainingStatus.PENDING
                )
                db.add(job)
            
            # Update job status
            if result.get("job_id"):
                job.shunya_job_id = result["job_id"]
                job.status = PersonalOttoTrainingStatus.RUNNING
                job.last_error = None
            else:
                job.status = PersonalOttoTrainingStatus.FAILED
                job.last_error = result.get("message", "Unknown error")
            
            job.job_metadata = {
                "force_retrain": force_retrain,
                "estimated_completion_time": result.get("estimated_completion_time")
            }
            
            db.commit()
            
            return result
            
        except Exception as e:
            logger.error(
                f"Failed to trigger Personal Otto training for rep {rep_id}: {str(e)}",
                extra={"rep_id": rep_id, "company_id": company_id},
                exc_info=True
            )
            raise
    
    async def get_status_for_rep(
        self,
        db: Session,
        company_id: str,
        rep_id: str,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Get Personal Otto training status for a sales rep.
        
        Args:
            db: Database session
            company_id: Tenant/company ID
            rep_id: Sales rep user ID
            request_id: Correlation ID
        
        Returns:
            Status response with is_trained, training_status, etc.
        """
        try:
            # Call Shunya with REQUIRED target_role="sales_rep"
            shunya_status = await self.uwc_client.get_personal_otto_status(
                company_id=company_id,
                request_id=request_id,
                rep_id=rep_id,
                target_role=self.target_role  # REQUIRED: Always sales_rep
            )
            
            # Get local job record if exists
            job = db.query(PersonalOttoTrainingJob).filter(
                PersonalOttoTrainingJob.company_id == company_id,
                PersonalOttoTrainingJob.rep_id == rep_id
            ).first()
            
            # Merge Shunya status with local job status
            result = {
                **shunya_status,
                "local_job_id": job.id if job else None,
                "local_status": job.status.value if job and job.status else None,
                "last_trained_at": (
                    job.last_trained_at.isoformat() if job and job.last_trained_at
                    else shunya_status.get("last_trained_at")
                )
            }
            
            return result
            
        except Exception as e:
            logger.error(
                f"Failed to get Personal Otto status for rep {rep_id}: {str(e)}",
                extra={"rep_id": rep_id, "company_id": company_id},
                exc_info=True
            )
            raise
    
    async def get_profile_for_rep(
        self,
        db: Session,
        company_id: str,
        rep_id: str,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Get Personal Otto profile for a sales rep.
        
        Args:
            db: Database session
            company_id: Tenant/company ID
            rep_id: Sales rep user ID
            request_id: Correlation ID
        
        Returns:
            Profile response with personality_traits, writing_style, etc.
        """
        try:
            # Call Shunya with REQUIRED target_role="sales_rep"
            profile = await self.uwc_client.get_personal_otto_profile(
                company_id=company_id,
                request_id=request_id,
                rep_id=rep_id,
                target_role=self.target_role  # REQUIRED: Always sales_rep
            )
            
            return profile
            
        except Exception as e:
            logger.error(
                f"Failed to get Personal Otto profile for rep {rep_id}: {str(e)}",
                extra={"rep_id": rep_id, "company_id": company_id},
                exc_info=True
            )
            raise


# Singleton instance
personal_otto_service = PersonalOttoService()

