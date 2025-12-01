"""
Utilities for extracting and handling Shunya job IDs from responses.
"""
from typing import Optional, Dict, Any


def extract_shunya_job_id(response: Dict[str, Any], job_type: str = "analysis") -> Optional[str]:
    """
    Extract Shunya job ID from API response.
    
    Shunya may return job IDs in different fields:
    - task_id (string)
    - job_id (string)
    - transcript_id (integer, may need conversion)
    - id (string)
    
    Args:
        response: Shunya API response
        job_type: Type of job ("transcription", "analysis", "segmentation")
    
    Returns:
        Job ID string or None if not found
    """
    if not isinstance(response, dict):
        return None
    
    # Try common job ID fields (in order of preference)
    job_id_fields = ["job_id", "task_id", "transcript_id", "id"]
    
    for field in job_id_fields:
        value = response.get(field)
        if value is not None:
            # Convert to string if integer
            if isinstance(value, int):
                return str(value)
            if isinstance(value, str) and value.strip():
                return value.strip()
    
    # For transcription, check nested structures
    if job_type == "transcription" and "transcript_id" in response:
        transcript_id = response.get("transcript_id")
        if transcript_id is not None:
            return str(transcript_id)
    
    return None


def extract_call_id_from_payload(input_payload: Dict[str, Any]) -> Optional[int]:
    """Extract call_id from job input payload."""
    if not isinstance(input_payload, dict):
        return None
    
    call_id = input_payload.get("call_id")
    if call_id is not None:
        try:
            return int(call_id)
        except (ValueError, TypeError):
            pass
    
    return None



