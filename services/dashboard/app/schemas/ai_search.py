"""
Schemas for AI search endpoints (internal Ask Otto API).
"""
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class AISearchFilters(BaseModel):
    """Filters for AI search queries."""
    date_from: Optional[datetime] = Field(None, description="Start date for search")
    date_to: Optional[datetime] = Field(None, description="End date for search")
    rep_ids: Optional[List[str]] = Field(None, description="Filter by rep IDs")
    lead_statuses: Optional[List[str]] = Field(None, description="Filter by lead statuses")
    appointment_outcomes: Optional[List[str]] = Field(None, description="Filter by appointment outcomes")
    has_objections: Optional[bool] = Field(None, description="Filter by whether calls have objections")
    objection_labels: Optional[List[str]] = Field(None, description="Filter by objection labels")
    sentiment_min: Optional[float] = Field(None, description="Minimum sentiment score")
    sentiment_max: Optional[float] = Field(None, description="Maximum sentiment score")
    min_sop_score: Optional[float] = Field(None, description="Minimum SOP compliance score")
    max_sop_score: Optional[float] = Field(None, description="Maximum SOP compliance score")


class AISearchOptions(BaseModel):
    """Options for AI search queries."""
    sort_by: Optional[str] = Field(None, description="Sort field (e.g., 'started_at', '-started_at', 'sentiment_score')")
    offset: int = Field(0, description="Pagination offset")
    limit: int = Field(100, description="Pagination limit")
    include_calls: bool = Field(True, description="Whether to include call items in response")
    include_aggregates: bool = Field(True, description="Whether to include aggregate analytics")


class AISearchRequest(BaseModel):
    """Request schema for AI search endpoint."""
    filters: AISearchFilters = Field(..., description="Search filters")
    options: AISearchOptions = Field(default_factory=AISearchOptions, description="Search options")


class AISearchCallItem(BaseModel):
    """Schema for a single call item in search results."""
    call_id: str = Field(..., description="Call ID")
    rep_id: Optional[str] = Field(None, description="Assigned rep ID")
    lead_id: Optional[str] = Field(None, description="Associated lead ID")
    appointment_id: Optional[str] = Field(None, description="Associated appointment ID")
    contact_card_id: Optional[str] = Field(None, description="Associated contact card ID")
    company_id: str = Field(..., description="Company ID")
    started_at: datetime = Field(..., description="Call start time")
    ended_at: Optional[datetime] = Field(None, description="Call end time")
    duration_seconds: Optional[int] = Field(None, description="Call duration in seconds")
    outcome: Optional[str] = Field(None, description="Call outcome")
    sentiment_score: Optional[float] = Field(None, description="Sentiment score")
    main_objection_label: Optional[str] = Field(None, description="Main objection label")
    has_objections: bool = Field(False, description="Whether call has objections")
    sop_score: Optional[float] = Field(None, description="SOP compliance score")


class AISearchAggregates(BaseModel):
    """Aggregate analytics for search results."""
    total_calls: int = Field(..., description="Total number of calls matching filters")
    calls_by_outcome: Dict[str, int] = Field(default_factory=dict, description="Count of calls by outcome")
    calls_by_rep: Dict[str, int] = Field(default_factory=dict, description="Count of calls by rep")
    calls_with_objections: int = Field(0, description="Number of calls with objections")
    objection_label_counts: Dict[str, int] = Field(default_factory=dict, description="Count of each objection label")
    avg_sentiment: Optional[float] = Field(None, description="Average sentiment score")
    avg_sop_score: Optional[float] = Field(None, description="Average SOP compliance score")


class AISearchResponse(BaseModel):
    """Response schema for AI search endpoint."""
    calls: List[AISearchCallItem] = Field(default_factory=list, description="List of matching calls")
    aggregates: Optional[AISearchAggregates] = Field(None, description="Aggregate analytics")


