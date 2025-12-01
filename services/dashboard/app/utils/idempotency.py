"""
Idempotency utilities for Shunya-driven domain mutations.

Provides helpers for:
- Generating natural keys for Tasks and KeySignals
- Checking for existing entities before creation
- Hash computation for output payloads
"""
import hashlib
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.task import Task, TaskSource
from app.models.key_signal import KeySignal, SignalType


def generate_task_unique_key(
    source: TaskSource,
    description: str,
    contact_card_id: str,
) -> str:
    """
    Generate unique key for a task to prevent duplicates.
    
    Args:
        source: Task source (SHUNYA, OTTO, MANUAL)
        description: Task description text
        contact_card_id: Contact card ID
    
    Returns:
        SHA256 hash of (source, description, contact_card_id)
    """
    key_string = f"{source.value}:{description}:{contact_card_id}"
    return hashlib.sha256(key_string.encode()).hexdigest()


def generate_signal_unique_key(
    signal_type: SignalType,
    title: str,
    contact_card_id: str,
) -> str:
    """
    Generate unique key for a key signal to prevent duplicates.
    
    Args:
        signal_type: Signal type (RISK, OPPORTUNITY, COACHING, OPERATIONAL)
        title: Signal title text
        contact_card_id: Contact card ID
    
    Returns:
        SHA256 hash of (signal_type, title, contact_card_id)
    """
    key_string = f"{signal_type.value}:{title}:{contact_card_id}"
    return hashlib.sha256(key_string.encode()).hexdigest()


def generate_output_payload_hash(output_payload: Dict[str, Any]) -> str:
    """
    Generate hash of Shunya output payload for idempotency checking.
    
    Args:
        output_payload: Normalized Shunya output
    
    Returns:
        SHA256 hash of JSON-serialized payload (sorted keys)
    """
    # Normalize by sorting keys and removing timestamp fields
    normalized = {
        k: v for k, v in output_payload.items()
        if k not in ["processed_at", "created_at", "analyzed_at", "timestamp"]
    }
    payload_json = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(payload_json.encode()).hexdigest()


def task_exists_by_unique_key(
    db: Session,
    company_id: str,
    unique_key: str,
) -> bool:
    """
    Check if a task with the given unique key already exists.
    
    Args:
        db: Database session
        company_id: Company/tenant ID
        unique_key: Task unique key
    
    Returns:
        True if task exists, False otherwise
    """
    existing = db.query(Task).filter(
        Task.company_id == company_id,
        Task.unique_key == unique_key,
        Task.status != "cancelled",  # Don't consider cancelled tasks
    ).first()
    return existing is not None


def signal_exists_by_unique_key(
    db: Session,
    company_id: str,
    unique_key: str,
) -> bool:
    """
    Check if a key signal with the given unique key already exists.
    
    Args:
        db: Database session
        company_id: Company/tenant ID
        unique_key: Signal unique key
    
    Returns:
        True if signal exists, False otherwise
    """
    existing = db.query(KeySignal).filter(
        KeySignal.company_id == company_id,
        KeySignal.unique_key == unique_key,
        KeySignal.acknowledged == False,  # Don't consider acknowledged signals
    ).first()
    return existing is not None



