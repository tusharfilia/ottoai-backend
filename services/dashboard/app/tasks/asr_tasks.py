"""
ASR (Automatic Speech Recognition) background tasks
"""
from celery import current_task
from app.celery_app import celery_app
from app.services.uwc_client import UWCClient
from app.core.pii_masking import PIISafeLogger
import logging

logger = PIISafeLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def process_audio_transcription(self, audio_url: str, call_id: str, tenant_id: str):
    """
    Process audio file for transcription using UWC ASR (single provider)
    """
    try:
        logger.info(f"Starting transcription for call {call_id}")
        
        # Initialize client
        uwc_client = UWCClient()
        
        # Try UWC ASR first
        try:
            result = uwc_client.transcribe_audio(audio_url)
            if result and result.get("transcript"):
                logger.info(f"UWC transcription successful for call {call_id}")
                return {
                    "success": True,
                    "provider": "uwc",
                    "transcript": result["transcript"],
                    "confidence": result.get("confidence", 0.0),
                    "language": result.get("language", "en"),
                    "call_id": call_id,
                    "tenant_id": tenant_id
                }
        except Exception as e:
            logger.warning(f"UWC ASR failed for call {call_id}: {str(e)}")
        
        # No fallback provider configured
        logger.error(f"ASR transcription failed for call {call_id} via UWC; no fallback configured")
        raise RuntimeError("ASR provider unavailable")
        
    except Exception as e:
        logger.error(f"Transcription failed for call {call_id}: {str(e)}")
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))

@celery_app.task
def process_pending_transcriptions():
    """
    Process any pending transcription tasks
    """
    logger.info("Processing pending transcriptions")
    # Implementation for processing pending tasks
    pass

@celery_app.task(bind=True, max_retries=3)
def transcribe_with_retry(self, audio_url: str, call_id: str, tenant_id: str):
    """
    Retry transcription with exponential backoff
    """
    try:
        return process_audio_transcription(audio_url, call_id, tenant_id)
    except Exception as e:
        logger.error(f"Transcription retry failed for call {call_id}: {str(e)}")
        raise self.retry(countdown=60 * (2 ** self.request.retries))
