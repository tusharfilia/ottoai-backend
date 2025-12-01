"""
Pydantic schemas for internal AI search endpoint.

Used by Ask Otto to search and analyze calls with structured filters.
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class AISearchFilters(BaseModel):
    """Filters for call search."""
    rep_ids: Optional[List[str]] = Field(None, description="Filter by sales rep IDs")
    lead_statuses: Optional[List[str]] = Field(None, description="Filter by lead statuses (e.g., new, qualified_booked)")
    appointment_outcomes: Optional[List[str]] = Field(None, description="Filter by appointment outcomes (e.g., won, lost, pending)")
    call_directions: Optional[List[str]] = Field(None, description="Filter by call direction (inbound/outbound) - if available")
    has_objections: Optional[bool] = Field(None, description="Filter calls with/without objections")
    objection_labels: Optional[List[str]] = Field(None, description="Filter by specific objection labels (e.g., price, timeline)")
    sentiment_min: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum sentiment score (0.0-1.0)")
    sentiment_max: Optional[float] = Field(None, ge=0.0, le=1.0, description="Maximum sentiment score (0.0-1.0)")
    date_from: Optional[datetime] = Field(None, description="Filter calls from this date (defaults to 30 days ago)")
    date_to: Optional[datetime] = Field(None, description="Filter calls until this date (defaults to now)")
    min_sop_score: Optional[float] = Field(None, ge=0.0, le=10.0, description="Minimum SOP compliance score (0-10)")
    max_sop_score: Optional[float] = Field(None, ge=0.0, le=10.0, description="Maximum SOP compliance score (0-10)")


class AISearchOptions(BaseModel):
    """Options for search behavior."""
    include_calls: bool = Field(True, description="Include call list in response")
    include_aggregates: bool = Field(True, description="Include aggregate analytics in response")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of calls to return")
    offset: int = Field(0, ge=0, description="Offset for pagination")
    sort_by: Optional[str] = Field("started_at", description="Sort field (started_at, -started_at, sentiment_score, -sentiment_score)")


class AISearchRequest(BaseModel):
    """Request body for internal AI search endpoint."""
    filters: AISearchFilters
    options: AISearchOptions = Field(default_factory=AISearchOptions)


class AISearchCallItem(BaseModel):
    """Lightweight call metadata for search results."""
    call_id: int
    rep_id: Optional[str] = None
    lead_id: Optional[str] = None
    appointment_id: Optional[str] = None
    contact_card_id: Optional[str] = None
    company_id: str
    
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    outcome: Optional[str] = None  # Derived from lead/appointment status
    sentiment_score: Optional[float] = None
    main_objection_label: Optional[str] = None
    has_objections: bool = False
    sop_score: Optional[float] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AISearchAggregates(BaseModel):
    """Aggregate analytics over filtered calls."""
    total_calls: int
    calls_by_outcome: Dict[str, int] = Field(default_factory=dict)
    calls_by_rep: Dict[str, int] = Field(default_factory=dict)
    calls_with_objections: int = 0
    objection_label_counts: Dict[str, int] = Field(default_factory=dict)
    avg_sentiment: Optional[float] = None
    avg_sop_score: Optional[float] = None


class AISearchResponse(BaseModel):
    """Response for internal AI search endpoint."""
    calls: List[AISearchCallItem] = Field(default_factory=list)
    aggregates: Optional[AISearchAggregates] = None
    
    class Config:
        from_attributes = True


Pydantic schemas for internal AI search endpoint.

Used by Ask Otto to search and analyze calls with structured filters.
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class AISearchFilters(BaseModel):
    """Filters for call search."""
    rep_ids: Optional[List[str]] = Field(None, description="Filter by sales rep IDs")
    lead_statuses: Optional[List[str]] = Field(None, description="Filter by lead statuses (e.g., new, qualified_booked)")
    appointment_outcomes: Optional[List[str]] = Field(None, description="Filter by appointment outcomes (e.g., won, lost, pending)")
    call_directions: Optional[List[str]] = Field(None, description="Filter by call direction (inbound/outbound) - if available")
    has_objections: Optional[bool] = Field(None, description="Filter calls with/without objections")
    objection_labels: Optional[List[str]] = Field(None, description="Filter by specific objection labels (e.g., price, timeline)")
    sentiment_min: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum sentiment score (0.0-1.0)")
    sentiment_max: Optional[float] = Field(None, ge=0.0, le=1.0, description="Maximum sentiment score (0.0-1.0)")
    date_from: Optional[datetime] = Field(None, description="Filter calls from this date (defaults to 30 days ago)")
    date_to: Optional[datetime] = Field(None, description="Filter calls until this date (defaults to now)")
    min_sop_score: Optional[float] = Field(None, ge=0.0, le=10.0, description="Minimum SOP compliance score (0-10)")
    max_sop_score: Optional[float] = Field(None, ge=0.0, le=10.0, description="Maximum SOP compliance score (0-10)")


class AISearchOptions(BaseModel):
    """Options for search behavior."""
    include_calls: bool = Field(True, description="Include call list in response")
    include_aggregates: bool = Field(True, description="Include aggregate analytics in response")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of calls to return")
    offset: int = Field(0, ge=0, description="Offset for pagination")
    sort_by: Optional[str] = Field("started_at", description="Sort field (started_at, -started_at, sentiment_score, -sentiment_score)")


class AISearchRequest(BaseModel):
    """Request body for internal AI search endpoint."""
    filters: AISearchFilters
    options: AISearchOptions = Field(default_factory=AISearchOptions)


class AISearchCallItem(BaseModel):
    """Lightweight call metadata for search results."""
    call_id: int
    rep_id: Optional[str] = None
    lead_id: Optional[str] = None
    appointment_id: Optional[str] = None
    contact_card_id: Optional[str] = None
    company_id: str
    
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    outcome: Optional[str] = None  # Derived from lead/appointment status
    sentiment_score: Optional[float] = None
    main_objection_label: Optional[str] = None
    has_objections: bool = False
    sop_score: Optional[float] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AISearchAggregates(BaseModel):
    """Aggregate analytics over filtered calls."""
    total_calls: int
    calls_by_outcome: Dict[str, int] = Field(default_factory=dict)
    calls_by_rep: Dict[str, int] = Field(default_factory=dict)
    calls_with_objections: int = 0
    objection_label_counts: Dict[str, int] = Field(default_factory=dict)
    avg_sentiment: Optional[float] = None
    avg_sop_score: Optional[float] = None


class AISearchResponse(BaseModel):
    """Response for internal AI search endpoint."""
    calls: List[AISearchCallItem] = Field(default_factory=list)
    aggregates: Optional[AISearchAggregates] = None
    
    class Config:
        from_attributes = True


Pydantic schemas for internal AI search endpoint.

Used by Ask Otto to search and analyze calls with structured filters.
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class AISearchFilters(BaseModel):
    """Filters for call search."""
    rep_ids: Optional[List[str]] = Field(None, description="Filter by sales rep IDs")
    lead_statuses: Optional[List[str]] = Field(None, description="Filter by lead statuses (e.g., new, qualified_booked)")
    appointment_outcomes: Optional[List[str]] = Field(None, description="Filter by appointment outcomes (e.g., won, lost, pending)")
    call_directions: Optional[List[str]] = Field(None, description="Filter by call direction (inbound/outbound) - if available")
    has_objections: Optional[bool] = Field(None, description="Filter calls with/without objections")
    objection_labels: Optional[List[str]] = Field(None, description="Filter by specific objection labels (e.g., price, timeline)")
    sentiment_min: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum sentiment score (0.0-1.0)")
    sentiment_max: Optional[float] = Field(None, ge=0.0, le=1.0, description="Maximum sentiment score (0.0-1.0)")
    date_from: Optional[datetime] = Field(None, description="Filter calls from this date (defaults to 30 days ago)")
    date_to: Optional[datetime] = Field(None, description="Filter calls until this date (defaults to now)")
    min_sop_score: Optional[float] = Field(None, ge=0.0, le=10.0, description="Minimum SOP compliance score (0-10)")
    max_sop_score: Optional[float] = Field(None, ge=0.0, le=10.0, description="Maximum SOP compliance score (0-10)")


class AISearchOptions(BaseModel):
    """Options for search behavior."""
    include_calls: bool = Field(True, description="Include call list in response")
    include_aggregates: bool = Field(True, description="Include aggregate analytics in response")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of calls to return")
    offset: int = Field(0, ge=0, description="Offset for pagination")
    sort_by: Optional[str] = Field("started_at", description="Sort field (started_at, -started_at, sentiment_score, -sentiment_score)")


class AISearchRequest(BaseModel):
    """Request body for internal AI search endpoint."""
    filters: AISearchFilters
    options: AISearchOptions = Field(default_factory=AISearchOptions)


class AISearchCallItem(BaseModel):
    """Lightweight call metadata for search results."""
    call_id: int
    rep_id: Optional[str] = None
    lead_id: Optional[str] = None
    appointment_id: Optional[str] = None
    contact_card_id: Optional[str] = None
    company_id: str
    
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    outcome: Optional[str] = None  # Derived from lead/appointment status
    sentiment_score: Optional[float] = None
    main_objection_label: Optional[str] = None
    has_objections: bool = False
    sop_score: Optional[float] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AISearchAggregates(BaseModel):
    """Aggregate analytics over filtered calls."""
    total_calls: int
    calls_by_outcome: Dict[str, int] = Field(default_factory=dict)
    calls_by_rep: Dict[str, int] = Field(default_factory=dict)
    calls_with_objections: int = 0
    objection_label_counts: Dict[str, int] = Field(default_factory=dict)
    avg_sentiment: Optional[float] = None
    avg_sop_score: Optional[float] = None


class AISearchResponse(BaseModel):
    """Response for internal AI search endpoint."""
    calls: List[AISearchCallItem] = Field(default_factory=list)
    aggregates: Optional[AISearchAggregates] = None
    
    class Config:
        from_attributes = True


