"""
Adapter layer for Shunya API responses.

This module provides adapters for translating Shunya's API responses into Otto's
internal format. Use adapters when Shunya's format differs from Otto's expectations.

All adapters are designed to be backwards-compatible and handle missing fields gracefully.
"""
from typing import Optional, Dict, Any, List
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class ShunyaOutcomeAdapter:
    """
    Adapter for translating Shunya outcome values to Otto enums.
    
    TODO: Update mapping once Shunya confirms exact outcome string values.
    """
    
    # CSR call outcomes (from Responsibility Matrix - pending Shunya confirmation)
    CSR_OUTCOME_MAPPING = {
        "qualified_and_booked": "qualified_booked",
        "qualified_not_booked": "qualified_unbooked",
        "qualified_service_not_offered": "qualified_service_not_offered",
        "not_qualified": "not_qualified",
        # Aliases (handle variations)
        "qualified": "qualified_unbooked",
        "booked": "qualified_booked",
        "unqualified": "not_qualified",
    }
    
    # Sales visit outcomes (from Responsibility Matrix - pending Shunya confirmation)
    VISIT_OUTCOME_MAPPING = {
        "won": "won",
        "lost": "lost",
        "pending_decision": "pending",
        "no_show": "no_show",
        "rescheduled": "pending",  # Treat rescheduled as pending
        # Aliases
        "closed_won": "won",
        "closed_lost": "lost",
    }
    
    @classmethod
    def normalize_csr_outcome(cls, shunya_value: Optional[str]) -> Optional[str]:
        """
        Normalize CSR call outcome from Shunya to Otto format.
        
        Args:
            shunya_value: Raw outcome value from Shunya
        
        Returns:
            Normalized outcome value for Otto, or None if invalid
        """
        if not shunya_value:
            return None
        
        normalized = shunya_value.lower().strip()
        return cls.CSR_OUTCOME_MAPPING.get(normalized, normalized)
    
    @classmethod
    def normalize_visit_outcome(cls, shunya_value: Optional[str]) -> Optional[str]:
        """
        Normalize sales visit outcome from Shunya to Otto format.
        
        Args:
            shunya_value: Raw outcome value from Shunya
        
        Returns:
            Normalized outcome value for Otto, or None if invalid
        """
        if not shunya_value:
            return None
        
        normalized = shunya_value.lower().strip()
        return cls.VISIT_OUTCOME_MAPPING.get(normalized, normalized)


class ShunyaObjectionAdapter:
    """
    Adapter for normalizing Shunya objection taxonomy.
    
    TODO: Update taxonomy once Shunya provides complete objection label list.
    """
    
    # Standardized objection labels (pending Shunya confirmation)
    VALID_OBJECTION_LABELS = [
        "price",
        "timing",
        "trust",
        "competitor",
        "need",
        "authority",
        # TODO: Add more labels once Shunya confirms taxonomy
    ]
    
    @classmethod
    def normalize_objection_label(cls, label: Optional[str]) -> Optional[str]:
        """
        Normalize objection label from Shunya to Otto format.
        
        Args:
            label: Raw objection label from Shunya
        
        Returns:
            Normalized label, or None if invalid
        """
        if not label:
            return None
        
        normalized = label.lower().strip()
        
        # Validate against known taxonomy (if provided)
        # For now, return as-is; validation can be added once taxonomy is confirmed
        if normalized in cls.VALID_OBJECTION_LABELS:
            return normalized
        
        # Return lowercase version even if not in taxonomy (for backwards compatibility)
        return normalized
    
    @classmethod
    def extract_objection_labels(cls, objections: List[Dict[str, Any]]) -> List[str]:
        """
        Extract and normalize objection labels from Shunya objections.
        
        Args:
            objections: List of objection objects from Shunya
        
        Returns:
            List of normalized objection labels
        """
        labels = []
        for obj in objections:
            if isinstance(obj, dict):
                label = obj.get("objection_label") or obj.get("label") or obj.get("category")
                normalized = cls.normalize_objection_label(label)
                if normalized:
                    labels.append(normalized)
        
        return list(set(labels))  # Deduplicate


class ShunyaWebhookAdapter:
    """
    Adapter for parsing Shunya webhook payloads.
    
    TODO: Update structure once Shunya confirms final webhook schema.
    """
    
    @classmethod
    def parse_webhook_payload(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and normalize Shunya webhook payload.
        
        Args:
            payload: Raw webhook payload from Shunya
        
        Returns:
            Normalized payload with expected fields
        """
        normalized = {
            "shunya_job_id": payload.get("shunya_job_id") or payload.get("job_id") or payload.get("task_id"),
            "status": (payload.get("status") or "").lower(),
            "company_id": payload.get("company_id"),
            "result": payload.get("result") or payload.get("data"),
            "error": payload.get("error") or payload.get("error_message"),
            "timestamp": payload.get("timestamp") or payload.get("created_at"),
        }
        
        return normalized


class ShunyaSegmentationAdapter:
    """
    Adapter for handling additional segmentation fields.
    
    TODO: Update once Shunya adds new segmentation fields beyond Part1/Part2.
    """
    
    @classmethod
    def normalize_segmentation_response(cls, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize meeting segmentation response from Shunya.
        
        Currently handles Part1/Part2. Can be extended for additional parts.
        
        Args:
            response: Raw segmentation response from Shunya
        
        Returns:
            Normalized segmentation data
        """
        normalized = {
            "part1": response.get("part1") or {},
            "part2": response.get("part2") or {},
            # TODO: Add Part3, Part4, etc. once Shunya confirms structure
            "outcome": (response.get("outcome") or "").lower(),
            "segmentation_confidence": response.get("segmentation_confidence") or response.get("confidence"),
            "transition_point": response.get("transition_point"),
            "meeting_structure_score": response.get("meeting_structure_score"),
        }
        
        return normalized


class ShunyaErrorAdapter:
    """
    Adapter for parsing Shunya error envelopes.
    
    TODO: Update once Shunya confirms standardized error format.
    """
    
    @classmethod
    def parse_error_response(cls, response: Any) -> Dict[str, Any]:
        """
        Parse Shunya error response into standardized format.
        
        Args:
            response: Error response from Shunya (may be dict or string)
        
        Returns:
            Standardized error dictionary
        """
        if isinstance(response, dict):
            error_obj = response.get("error") or response
            return {
                "code": error_obj.get("code") or "UNKNOWN_ERROR",
                "message": error_obj.get("message") or str(response),
                "details": error_obj.get("details") or {},
                "retryable": error_obj.get("retryable", False),
            }
        
        # Fallback: treat as string message
        return {
            "code": "UNKNOWN_ERROR",
            "message": str(response),
            "details": {},
            "retryable": False,
        }


# Global adapter instances (if needed)
outcome_adapter = ShunyaOutcomeAdapter()
objection_adapter = ShunyaObjectionAdapter()
webhook_adapter = ShunyaWebhookAdapter()
segmentation_adapter = ShunyaSegmentationAdapter()
error_adapter = ShunyaErrorAdapter()


Adapter layer for Shunya API responses.

This module provides adapters for translating Shunya's API responses into Otto's
internal format. Use adapters when Shunya's format differs from Otto's expectations.

All adapters are designed to be backwards-compatible and handle missing fields gracefully.
"""
from typing import Optional, Dict, Any, List
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class ShunyaOutcomeAdapter:
    """
    Adapter for translating Shunya outcome values to Otto enums.
    
    TODO: Update mapping once Shunya confirms exact outcome string values.
    """
    
    # CSR call outcomes (from Responsibility Matrix - pending Shunya confirmation)
    CSR_OUTCOME_MAPPING = {
        "qualified_and_booked": "qualified_booked",
        "qualified_not_booked": "qualified_unbooked",
        "qualified_service_not_offered": "qualified_service_not_offered",
        "not_qualified": "not_qualified",
        # Aliases (handle variations)
        "qualified": "qualified_unbooked",
        "booked": "qualified_booked",
        "unqualified": "not_qualified",
    }
    
    # Sales visit outcomes (from Responsibility Matrix - pending Shunya confirmation)
    VISIT_OUTCOME_MAPPING = {
        "won": "won",
        "lost": "lost",
        "pending_decision": "pending",
        "no_show": "no_show",
        "rescheduled": "pending",  # Treat rescheduled as pending
        # Aliases
        "closed_won": "won",
        "closed_lost": "lost",
    }
    
    @classmethod
    def normalize_csr_outcome(cls, shunya_value: Optional[str]) -> Optional[str]:
        """
        Normalize CSR call outcome from Shunya to Otto format.
        
        Args:
            shunya_value: Raw outcome value from Shunya
        
        Returns:
            Normalized outcome value for Otto, or None if invalid
        """
        if not shunya_value:
            return None
        
        normalized = shunya_value.lower().strip()
        return cls.CSR_OUTCOME_MAPPING.get(normalized, normalized)
    
    @classmethod
    def normalize_visit_outcome(cls, shunya_value: Optional[str]) -> Optional[str]:
        """
        Normalize sales visit outcome from Shunya to Otto format.
        
        Args:
            shunya_value: Raw outcome value from Shunya
        
        Returns:
            Normalized outcome value for Otto, or None if invalid
        """
        if not shunya_value:
            return None
        
        normalized = shunya_value.lower().strip()
        return cls.VISIT_OUTCOME_MAPPING.get(normalized, normalized)


class ShunyaObjectionAdapter:
    """
    Adapter for normalizing Shunya objection taxonomy.
    
    TODO: Update taxonomy once Shunya provides complete objection label list.
    """
    
    # Standardized objection labels (pending Shunya confirmation)
    VALID_OBJECTION_LABELS = [
        "price",
        "timing",
        "trust",
        "competitor",
        "need",
        "authority",
        # TODO: Add more labels once Shunya confirms taxonomy
    ]
    
    @classmethod
    def normalize_objection_label(cls, label: Optional[str]) -> Optional[str]:
        """
        Normalize objection label from Shunya to Otto format.
        
        Args:
            label: Raw objection label from Shunya
        
        Returns:
            Normalized label, or None if invalid
        """
        if not label:
            return None
        
        normalized = label.lower().strip()
        
        # Validate against known taxonomy (if provided)
        # For now, return as-is; validation can be added once taxonomy is confirmed
        if normalized in cls.VALID_OBJECTION_LABELS:
            return normalized
        
        # Return lowercase version even if not in taxonomy (for backwards compatibility)
        return normalized
    
    @classmethod
    def extract_objection_labels(cls, objections: List[Dict[str, Any]]) -> List[str]:
        """
        Extract and normalize objection labels from Shunya objections.
        
        Args:
            objections: List of objection objects from Shunya
        
        Returns:
            List of normalized objection labels
        """
        labels = []
        for obj in objections:
            if isinstance(obj, dict):
                label = obj.get("objection_label") or obj.get("label") or obj.get("category")
                normalized = cls.normalize_objection_label(label)
                if normalized:
                    labels.append(normalized)
        
        return list(set(labels))  # Deduplicate


class ShunyaWebhookAdapter:
    """
    Adapter for parsing Shunya webhook payloads.
    
    TODO: Update structure once Shunya confirms final webhook schema.
    """
    
    @classmethod
    def parse_webhook_payload(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and normalize Shunya webhook payload.
        
        Args:
            payload: Raw webhook payload from Shunya
        
        Returns:
            Normalized payload with expected fields
        """
        normalized = {
            "shunya_job_id": payload.get("shunya_job_id") or payload.get("job_id") or payload.get("task_id"),
            "status": (payload.get("status") or "").lower(),
            "company_id": payload.get("company_id"),
            "result": payload.get("result") or payload.get("data"),
            "error": payload.get("error") or payload.get("error_message"),
            "timestamp": payload.get("timestamp") or payload.get("created_at"),
        }
        
        return normalized


class ShunyaSegmentationAdapter:
    """
    Adapter for handling additional segmentation fields.
    
    TODO: Update once Shunya adds new segmentation fields beyond Part1/Part2.
    """
    
    @classmethod
    def normalize_segmentation_response(cls, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize meeting segmentation response from Shunya.
        
        Currently handles Part1/Part2. Can be extended for additional parts.
        
        Args:
            response: Raw segmentation response from Shunya
        
        Returns:
            Normalized segmentation data
        """
        normalized = {
            "part1": response.get("part1") or {},
            "part2": response.get("part2") or {},
            # TODO: Add Part3, Part4, etc. once Shunya confirms structure
            "outcome": (response.get("outcome") or "").lower(),
            "segmentation_confidence": response.get("segmentation_confidence") or response.get("confidence"),
            "transition_point": response.get("transition_point"),
            "meeting_structure_score": response.get("meeting_structure_score"),
        }
        
        return normalized


class ShunyaErrorAdapter:
    """
    Adapter for parsing Shunya error envelopes.
    
    TODO: Update once Shunya confirms standardized error format.
    """
    
    @classmethod
    def parse_error_response(cls, response: Any) -> Dict[str, Any]:
        """
        Parse Shunya error response into standardized format.
        
        Args:
            response: Error response from Shunya (may be dict or string)
        
        Returns:
            Standardized error dictionary
        """
        if isinstance(response, dict):
            error_obj = response.get("error") or response
            return {
                "code": error_obj.get("code") or "UNKNOWN_ERROR",
                "message": error_obj.get("message") or str(response),
                "details": error_obj.get("details") or {},
                "retryable": error_obj.get("retryable", False),
            }
        
        # Fallback: treat as string message
        return {
            "code": "UNKNOWN_ERROR",
            "message": str(response),
            "details": {},
            "retryable": False,
        }


# Global adapter instances (if needed)
outcome_adapter = ShunyaOutcomeAdapter()
objection_adapter = ShunyaObjectionAdapter()
webhook_adapter = ShunyaWebhookAdapter()
segmentation_adapter = ShunyaSegmentationAdapter()
error_adapter = ShunyaErrorAdapter()


Adapter layer for Shunya API responses.

This module provides adapters for translating Shunya's API responses into Otto's
internal format. Use adapters when Shunya's format differs from Otto's expectations.

All adapters are designed to be backwards-compatible and handle missing fields gracefully.
"""
from typing import Optional, Dict, Any, List
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


class ShunyaOutcomeAdapter:
    """
    Adapter for translating Shunya outcome values to Otto enums.
    
    TODO: Update mapping once Shunya confirms exact outcome string values.
    """
    
    # CSR call outcomes (from Responsibility Matrix - pending Shunya confirmation)
    CSR_OUTCOME_MAPPING = {
        "qualified_and_booked": "qualified_booked",
        "qualified_not_booked": "qualified_unbooked",
        "qualified_service_not_offered": "qualified_service_not_offered",
        "not_qualified": "not_qualified",
        # Aliases (handle variations)
        "qualified": "qualified_unbooked",
        "booked": "qualified_booked",
        "unqualified": "not_qualified",
    }
    
    # Sales visit outcomes (from Responsibility Matrix - pending Shunya confirmation)
    VISIT_OUTCOME_MAPPING = {
        "won": "won",
        "lost": "lost",
        "pending_decision": "pending",
        "no_show": "no_show",
        "rescheduled": "pending",  # Treat rescheduled as pending
        # Aliases
        "closed_won": "won",
        "closed_lost": "lost",
    }
    
    @classmethod
    def normalize_csr_outcome(cls, shunya_value: Optional[str]) -> Optional[str]:
        """
        Normalize CSR call outcome from Shunya to Otto format.
        
        Args:
            shunya_value: Raw outcome value from Shunya
        
        Returns:
            Normalized outcome value for Otto, or None if invalid
        """
        if not shunya_value:
            return None
        
        normalized = shunya_value.lower().strip()
        return cls.CSR_OUTCOME_MAPPING.get(normalized, normalized)
    
    @classmethod
    def normalize_visit_outcome(cls, shunya_value: Optional[str]) -> Optional[str]:
        """
        Normalize sales visit outcome from Shunya to Otto format.
        
        Args:
            shunya_value: Raw outcome value from Shunya
        
        Returns:
            Normalized outcome value for Otto, or None if invalid
        """
        if not shunya_value:
            return None
        
        normalized = shunya_value.lower().strip()
        return cls.VISIT_OUTCOME_MAPPING.get(normalized, normalized)


class ShunyaObjectionAdapter:
    """
    Adapter for normalizing Shunya objection taxonomy.
    
    TODO: Update taxonomy once Shunya provides complete objection label list.
    """
    
    # Standardized objection labels (pending Shunya confirmation)
    VALID_OBJECTION_LABELS = [
        "price",
        "timing",
        "trust",
        "competitor",
        "need",
        "authority",
        # TODO: Add more labels once Shunya confirms taxonomy
    ]
    
    @classmethod
    def normalize_objection_label(cls, label: Optional[str]) -> Optional[str]:
        """
        Normalize objection label from Shunya to Otto format.
        
        Args:
            label: Raw objection label from Shunya
        
        Returns:
            Normalized label, or None if invalid
        """
        if not label:
            return None
        
        normalized = label.lower().strip()
        
        # Validate against known taxonomy (if provided)
        # For now, return as-is; validation can be added once taxonomy is confirmed
        if normalized in cls.VALID_OBJECTION_LABELS:
            return normalized
        
        # Return lowercase version even if not in taxonomy (for backwards compatibility)
        return normalized
    
    @classmethod
    def extract_objection_labels(cls, objections: List[Dict[str, Any]]) -> List[str]:
        """
        Extract and normalize objection labels from Shunya objections.
        
        Args:
            objections: List of objection objects from Shunya
        
        Returns:
            List of normalized objection labels
        """
        labels = []
        for obj in objections:
            if isinstance(obj, dict):
                label = obj.get("objection_label") or obj.get("label") or obj.get("category")
                normalized = cls.normalize_objection_label(label)
                if normalized:
                    labels.append(normalized)
        
        return list(set(labels))  # Deduplicate


class ShunyaWebhookAdapter:
    """
    Adapter for parsing Shunya webhook payloads.
    
    TODO: Update structure once Shunya confirms final webhook schema.
    """
    
    @classmethod
    def parse_webhook_payload(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse and normalize Shunya webhook payload.
        
        Args:
            payload: Raw webhook payload from Shunya
        
        Returns:
            Normalized payload with expected fields
        """
        normalized = {
            "shunya_job_id": payload.get("shunya_job_id") or payload.get("job_id") or payload.get("task_id"),
            "status": (payload.get("status") or "").lower(),
            "company_id": payload.get("company_id"),
            "result": payload.get("result") or payload.get("data"),
            "error": payload.get("error") or payload.get("error_message"),
            "timestamp": payload.get("timestamp") or payload.get("created_at"),
        }
        
        return normalized


class ShunyaSegmentationAdapter:
    """
    Adapter for handling additional segmentation fields.
    
    TODO: Update once Shunya adds new segmentation fields beyond Part1/Part2.
    """
    
    @classmethod
    def normalize_segmentation_response(cls, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize meeting segmentation response from Shunya.
        
        Currently handles Part1/Part2. Can be extended for additional parts.
        
        Args:
            response: Raw segmentation response from Shunya
        
        Returns:
            Normalized segmentation data
        """
        normalized = {
            "part1": response.get("part1") or {},
            "part2": response.get("part2") or {},
            # TODO: Add Part3, Part4, etc. once Shunya confirms structure
            "outcome": (response.get("outcome") or "").lower(),
            "segmentation_confidence": response.get("segmentation_confidence") or response.get("confidence"),
            "transition_point": response.get("transition_point"),
            "meeting_structure_score": response.get("meeting_structure_score"),
        }
        
        return normalized


class ShunyaErrorAdapter:
    """
    Adapter for parsing Shunya error envelopes.
    
    TODO: Update once Shunya confirms standardized error format.
    """
    
    @classmethod
    def parse_error_response(cls, response: Any) -> Dict[str, Any]:
        """
        Parse Shunya error response into standardized format.
        
        Args:
            response: Error response from Shunya (may be dict or string)
        
        Returns:
            Standardized error dictionary
        """
        if isinstance(response, dict):
            error_obj = response.get("error") or response
            return {
                "code": error_obj.get("code") or "UNKNOWN_ERROR",
                "message": error_obj.get("message") or str(response),
                "details": error_obj.get("details") or {},
                "retryable": error_obj.get("retryable", False),
            }
        
        # Fallback: treat as string message
        return {
            "code": "UNKNOWN_ERROR",
            "message": str(response),
            "details": {},
            "retryable": False,
        }


# Global adapter instances (if needed)
outcome_adapter = ShunyaOutcomeAdapter()
objection_adapter = ShunyaObjectionAdapter()
webhook_adapter = ShunyaWebhookAdapter()
segmentation_adapter = ShunyaSegmentationAdapter()
error_adapter = ShunyaErrorAdapter()


