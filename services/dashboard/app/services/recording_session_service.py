"""
Service for managing recording sessions with Ghost Mode support.
"""
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.recording_session import (
    RecordingSession,
    RecordingMode,
    AudioStorageMode,
)
from app.models.company import Company, GhostModeRetention, GhostModeStorage
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class RecordingSessionService:
    """
    Service for recording session operations with privacy-aware Ghost Mode.
    """
    
    def get_audio_storage_mode(
        self,
        mode: RecordingMode,
        company_id: str,
        db: Optional[Session] = None,
    ) -> AudioStorageMode:
        """
        Determine audio storage mode based on recording mode and tenant config.
        
        Args:
            mode: Recording mode (normal, ghost, off)
            company_id: Tenant/company ID
            db: Optional database session (if provided, fetches company config)
            
        Returns:
            AudioStorageMode (persistent, ephemeral, not_stored)
        """
        if mode == RecordingMode.OFF:
            return AudioStorageMode.NOT_STORED
        
        if mode == RecordingMode.GHOST:
            # Get from company config
            if db:
                company = db.query(Company).filter(Company.id == company_id).first()
                if company:
                    if company.ghost_mode_storage == GhostModeStorage.NOT_STORED:
                        return AudioStorageMode.NOT_STORED
                    elif company.ghost_mode_storage == GhostModeStorage.EPHEMERAL:
                        return AudioStorageMode.EPHEMERAL
            
            # Default: NOT_STORED (most private)
            return AudioStorageMode.NOT_STORED
        
        # Normal mode: persistent storage
        return AudioStorageMode.PERSISTENT
    
    def apply_ghost_mode_restrictions(
        self,
        session: RecordingSession,
        company_id: str,
        db: Optional[Session] = None,
    ) -> RecordingSession:
        """
        Apply Ghost Mode restrictions to a session for API responses.
        
        In Ghost Mode:
        - audio_url is always None (not exposed)
        - Full transcript may be restricted based on tenant config
        
        Args:
            session: RecordingSession instance
            company_id: Tenant/company ID
            db: Optional database session (if provided, fetches company config)
            
        Returns:
            Session with restrictions applied (modified in place)
        """
        if session.mode != RecordingMode.GHOST:
            return session
        
        # In Ghost Mode, never expose audio_url
        session.audio_url = None
        
        # Check if transcript should be restricted
        if db:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                if company.ghost_mode_retention == GhostModeRetention.NONE:
                    # Hide transcript if it exists
                    if hasattr(session, 'transcript') and session.transcript:
                        session.transcript.transcript_text = None
                elif company.ghost_mode_retention == GhostModeRetention.AGGREGATES_ONLY:
                    # Hide full transcript, only show aggregates
                    if hasattr(session, 'transcript') and session.transcript:
                        session.transcript.transcript_text = None
        
        return session
    
    def should_retain_transcript(
        self,
        session: RecordingSession,
        company_id: str,
        db: Optional[Session] = None,
    ) -> bool:
        """
        Determine if transcript should be retained in Ghost Mode.
        
        Args:
            session: RecordingSession instance
            company_id: Tenant/company ID
            db: Optional database session (if provided, fetches company config)
            
        Returns:
            True if transcript should be retained, False otherwise
        """
        if session.mode != RecordingMode.GHOST:
            return True  # Always retain in normal mode
        
        # Get from company config
        if db:
            company = db.query(Company).filter(Company.id == company_id).first()
            if company:
                if company.ghost_mode_retention == GhostModeRetention.NONE:
                    return False  # No transcript retention
                elif company.ghost_mode_retention == GhostModeRetention.AGGREGATES_ONLY:
                    return False  # No full transcript, only aggregates
                elif company.ghost_mode_retention == GhostModeRetention.MINIMAL:
                    return True  # Retain summary transcript
        
        # Default: Don't retain full transcript in Ghost Mode
        return False
    
    def should_retain_audio(
        self,
        session: RecordingSession,
    ) -> bool:
        """
        Determine if audio should be retained.
        
        Args:
            session: RecordingSession instance
            
        Returns:
            True if audio should be retained, False otherwise
        """
        return session.audio_storage_mode == AudioStorageMode.PERSISTENT
    
    def cleanup_ephemeral_sessions(
        self,
        db: Session,
        company_id: Optional[str] = None,
    ) -> int:
        """
        Clean up expired ephemeral recording sessions.
        
        Deletes sessions with expires_at < now and audio_storage_mode = EPHEMERAL.
        
        Args:
            db: Database session
            company_id: Optional tenant filter
            
        Returns:
            Number of sessions cleaned up
        """
        query = db.query(RecordingSession).filter(
            RecordingSession.audio_storage_mode == AudioStorageMode.EPHEMERAL,
            RecordingSession.expires_at < datetime.utcnow(),
        )
        
        if company_id:
            query = query.filter(RecordingSession.company_id == company_id)
        
        count = query.count()
        query.delete(synchronize_session=False)
        db.commit()
        
        logger.info(f"Cleaned up {count} expired ephemeral recording sessions")
        return count

