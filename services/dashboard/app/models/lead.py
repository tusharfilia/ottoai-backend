from datetime import datetime
import enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Float, Boolean, Index
from sqlalchemy.orm import relationship

from app.database import Base


class LeadStatus(str, enum.Enum):
    """Adaptive lead status engine (Section 3.4)."""
    NEW = "new"
    WARM = "warm"  # Showing interest but not urgent
    HOT = "hot"  # High urgency, ready to close
    QUALIFIED_BOOKED = "qualified_booked"
    QUALIFIED_UNBOOKED = "qualified_unbooked"
    QUALIFIED_SERVICE_NOT_OFFERED = "qualified_service_not_offered"
    NURTURING = "nurturing"
    DORMANT = "dormant"  # No activity for extended period
    ABANDONED = "abandoned"  # Customer stopped responding
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class DealStatus(str, enum.Enum):
    """Deal status for top section (Section 3.2)."""
    NEW = "new"
    NURTURING = "nurturing"
    BOOKED = "booked"
    NO_SHOW = "no-show"
    RESCHEDULED = "rescheduled"
    IN_PROGRESS = "in-progress"
    WON = "won"
    LOST = "lost"


class LeadSource(str, enum.Enum):
    UNKNOWN = "unknown"
    INBOUND_CALL = "inbound_call"
    INBOUND_WEB = "inbound_web"
    REFERRAL = "referral"
    PARTNER = "partner"
    OTHER = "other"


class PoolStatus(str, enum.Enum):
    """Lead pool status for shared lead management."""
    IN_POOL = "in_pool"  # Available in pool
    ASSIGNED = "assigned"  # Assigned to a rep
    CLOSED = "closed"  # Deal closed (won or lost)
    ARCHIVED = "archived"  # Archived/no longer active


class Lead(Base):
    """
    Lead generated from a contact interaction. Leads represent sales opportunities
    and aggregate calls, appointments, and Shunya classification outputs.
    """

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_company_status_contact", "company_id", "status", "contact_card_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    contact_card_id = Column(String, ForeignKey("contact_cards.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    status = Column(
        Enum(LeadStatus, native_enum=False, name="lead_status"),
        default=LeadStatus.NEW,
        nullable=False,
    )
    source = Column(
        Enum(LeadSource, native_enum=False, name="lead_source"),
        default=LeadSource.UNKNOWN,
        nullable=False,
    )
    campaign = Column(String, nullable=True)
    pipeline_stage = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    score = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)

    last_contacted_at = Column(DateTime, nullable=True)
    last_qualified_at = Column(DateTime, nullable=True)
    
    # Deal status fields (Section 3.2)
    deal_status = Column(String, nullable=True, comment="Computed: new/nurturing/booked/no-show/rescheduled/in-progress/won/lost")
    deal_size = Column(Float, nullable=True, comment="Deal size in dollars")
    deal_summary = Column(Text, nullable=True, comment="Deal summary text")
    closed_at = Column(DateTime, nullable=True, comment="When deal was closed (won or lost)")
    
    # Rep assignment tracking (Section 3.3)
    assigned_rep_id = Column(String, ForeignKey("sales_reps.user_id"), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True, comment="When rep was assigned")
    assigned_by = Column(String, nullable=True, comment="User ID who assigned this lead")
    rep_claimed = Column(Boolean, default=False, comment="Whether rep claimed this lead")
    
    # Lead Pool tracking (Section 2.2)
    pool_status = Column(
        Enum(PoolStatus, native_enum=False, name="pool_status"),
        default=PoolStatus.IN_POOL,
        nullable=False,
        index=True,
        comment="Lead pool status: in_pool/assigned/closed/archived"
    )
    requested_by_rep_ids = Column(JSON, nullable=True, comment="List of rep IDs who requested this lead (denormalized for quick access)")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    contact_card = relationship("ContactCard", back_populates="leads")
    company = relationship("Company", back_populates="leads")
    calls = relationship("Call", back_populates="lead")
    appointments = relationship("Appointment", back_populates="lead")
    recording_analyses = relationship("RecordingAnalysis", back_populates="lead")
    tasks = relationship("Task", back_populates="lead")
    key_signals = relationship("KeySignal", back_populates="lead")
    status_history = relationship("LeadStatusHistory", back_populates="lead", order_by="LeadStatusHistory.created_at.desc()")
    assignment_history = relationship("RepAssignmentHistory", back_populates="lead", order_by="RepAssignmentHistory.created_at.desc()")
    event_logs = relationship("EventLog", back_populates="lead", order_by="EventLog.created_at.desc()")
    assigned_rep = relationship("SalesRep", foreign_keys=[assigned_rep_id])

    def is_active(self) -> bool:
        return self.status in {LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.NURTURING, LeadStatus.BOOKED}


from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Float, Boolean, Index
from sqlalchemy.orm import relationship

from app.database import Base


class LeadStatus(str, enum.Enum):
    """Adaptive lead status engine (Section 3.4)."""
    NEW = "new"
    WARM = "warm"  # Showing interest but not urgent
    HOT = "hot"  # High urgency, ready to close
    QUALIFIED_BOOKED = "qualified_booked"
    QUALIFIED_UNBOOKED = "qualified_unbooked"
    QUALIFIED_SERVICE_NOT_OFFERED = "qualified_service_not_offered"
    NURTURING = "nurturing"
    DORMANT = "dormant"  # No activity for extended period
    ABANDONED = "abandoned"  # Customer stopped responding
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class DealStatus(str, enum.Enum):
    """Deal status for top section (Section 3.2)."""
    NEW = "new"
    NURTURING = "nurturing"
    BOOKED = "booked"
    NO_SHOW = "no-show"
    RESCHEDULED = "rescheduled"
    IN_PROGRESS = "in-progress"
    WON = "won"
    LOST = "lost"


class LeadSource(str, enum.Enum):
    UNKNOWN = "unknown"
    INBOUND_CALL = "inbound_call"
    INBOUND_WEB = "inbound_web"
    REFERRAL = "referral"
    PARTNER = "partner"
    OTHER = "other"


class PoolStatus(str, enum.Enum):
    """Lead pool status for shared lead management."""
    IN_POOL = "in_pool"  # Available in pool
    ASSIGNED = "assigned"  # Assigned to a rep
    CLOSED = "closed"  # Deal closed (won or lost)
    ARCHIVED = "archived"  # Archived/no longer active


class Lead(Base):
    """
    Lead generated from a contact interaction. Leads represent sales opportunities
    and aggregate calls, appointments, and Shunya classification outputs.
    """

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_company_status_contact", "company_id", "status", "contact_card_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    contact_card_id = Column(String, ForeignKey("contact_cards.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    status = Column(
        Enum(LeadStatus, native_enum=False, name="lead_status"),
        default=LeadStatus.NEW,
        nullable=False,
    )
    source = Column(
        Enum(LeadSource, native_enum=False, name="lead_source"),
        default=LeadSource.UNKNOWN,
        nullable=False,
    )
    campaign = Column(String, nullable=True)
    pipeline_stage = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    score = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)

    last_contacted_at = Column(DateTime, nullable=True)
    last_qualified_at = Column(DateTime, nullable=True)
    
    # Deal status fields (Section 3.2)
    deal_status = Column(String, nullable=True, comment="Computed: new/nurturing/booked/no-show/rescheduled/in-progress/won/lost")
    deal_size = Column(Float, nullable=True, comment="Deal size in dollars")
    deal_summary = Column(Text, nullable=True, comment="Deal summary text")
    closed_at = Column(DateTime, nullable=True, comment="When deal was closed (won or lost)")
    
    # Rep assignment tracking (Section 3.3)
    assigned_rep_id = Column(String, ForeignKey("sales_reps.user_id"), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True, comment="When rep was assigned")
    assigned_by = Column(String, nullable=True, comment="User ID who assigned this lead")
    rep_claimed = Column(Boolean, default=False, comment="Whether rep claimed this lead")
    
    # Lead Pool tracking (Section 2.2)
    pool_status = Column(
        Enum(PoolStatus, native_enum=False, name="pool_status"),
        default=PoolStatus.IN_POOL,
        nullable=False,
        index=True,
        comment="Lead pool status: in_pool/assigned/closed/archived"
    )
    requested_by_rep_ids = Column(JSON, nullable=True, comment="List of rep IDs who requested this lead (denormalized for quick access)")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    contact_card = relationship("ContactCard", back_populates="leads")
    company = relationship("Company", back_populates="leads")
    calls = relationship("Call", back_populates="lead")
    appointments = relationship("Appointment", back_populates="lead")
    recording_analyses = relationship("RecordingAnalysis", back_populates="lead")
    tasks = relationship("Task", back_populates="lead")
    key_signals = relationship("KeySignal", back_populates="lead")
    status_history = relationship("LeadStatusHistory", back_populates="lead", order_by="LeadStatusHistory.created_at.desc()")
    assignment_history = relationship("RepAssignmentHistory", back_populates="lead", order_by="RepAssignmentHistory.created_at.desc()")
    event_logs = relationship("EventLog", back_populates="lead", order_by="EventLog.created_at.desc()")
    assigned_rep = relationship("SalesRep", foreign_keys=[assigned_rep_id])

    def is_active(self) -> bool:
        return self.status in {LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.NURTURING, LeadStatus.BOOKED}


from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Float, Boolean, Index
from sqlalchemy.orm import relationship

from app.database import Base


class LeadStatus(str, enum.Enum):
    """Adaptive lead status engine (Section 3.4)."""
    NEW = "new"
    WARM = "warm"  # Showing interest but not urgent
    HOT = "hot"  # High urgency, ready to close
    QUALIFIED_BOOKED = "qualified_booked"
    QUALIFIED_UNBOOKED = "qualified_unbooked"
    QUALIFIED_SERVICE_NOT_OFFERED = "qualified_service_not_offered"
    NURTURING = "nurturing"
    DORMANT = "dormant"  # No activity for extended period
    ABANDONED = "abandoned"  # Customer stopped responding
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class DealStatus(str, enum.Enum):
    """Deal status for top section (Section 3.2)."""
    NEW = "new"
    NURTURING = "nurturing"
    BOOKED = "booked"
    NO_SHOW = "no-show"
    RESCHEDULED = "rescheduled"
    IN_PROGRESS = "in-progress"
    WON = "won"
    LOST = "lost"


class LeadSource(str, enum.Enum):
    UNKNOWN = "unknown"
    INBOUND_CALL = "inbound_call"
    INBOUND_WEB = "inbound_web"
    REFERRAL = "referral"
    PARTNER = "partner"
    OTHER = "other"


class PoolStatus(str, enum.Enum):
    """Lead pool status for shared lead management."""
    IN_POOL = "in_pool"  # Available in pool
    ASSIGNED = "assigned"  # Assigned to a rep
    CLOSED = "closed"  # Deal closed (won or lost)
    ARCHIVED = "archived"  # Archived/no longer active


class Lead(Base):
    """
    Lead generated from a contact interaction. Leads represent sales opportunities
    and aggregate calls, appointments, and Shunya classification outputs.
    """

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_company_status_contact", "company_id", "status", "contact_card_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    contact_card_id = Column(String, ForeignKey("contact_cards.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    status = Column(
        Enum(LeadStatus, native_enum=False, name="lead_status"),
        default=LeadStatus.NEW,
        nullable=False,
    )
    source = Column(
        Enum(LeadSource, native_enum=False, name="lead_source"),
        default=LeadSource.UNKNOWN,
        nullable=False,
    )
    campaign = Column(String, nullable=True)
    pipeline_stage = Column(String, nullable=True)
    priority = Column(String, nullable=True)
    score = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)

    last_contacted_at = Column(DateTime, nullable=True)
    last_qualified_at = Column(DateTime, nullable=True)
    
    # Deal status fields (Section 3.2)
    deal_status = Column(String, nullable=True, comment="Computed: new/nurturing/booked/no-show/rescheduled/in-progress/won/lost")
    deal_size = Column(Float, nullable=True, comment="Deal size in dollars")
    deal_summary = Column(Text, nullable=True, comment="Deal summary text")
    closed_at = Column(DateTime, nullable=True, comment="When deal was closed (won or lost)")
    
    # Rep assignment tracking (Section 3.3)
    assigned_rep_id = Column(String, ForeignKey("sales_reps.user_id"), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True, comment="When rep was assigned")
    assigned_by = Column(String, nullable=True, comment="User ID who assigned this lead")
    rep_claimed = Column(Boolean, default=False, comment="Whether rep claimed this lead")
    
    # Lead Pool tracking (Section 2.2)
    pool_status = Column(
        Enum(PoolStatus, native_enum=False, name="pool_status"),
        default=PoolStatus.IN_POOL,
        nullable=False,
        index=True,
        comment="Lead pool status: in_pool/assigned/closed/archived"
    )
    requested_by_rep_ids = Column(JSON, nullable=True, comment="List of rep IDs who requested this lead (denormalized for quick access)")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    contact_card = relationship("ContactCard", back_populates="leads")
    company = relationship("Company", back_populates="leads")
    calls = relationship("Call", back_populates="lead")
    appointments = relationship("Appointment", back_populates="lead")
    recording_analyses = relationship("RecordingAnalysis", back_populates="lead")
    tasks = relationship("Task", back_populates="lead")
    key_signals = relationship("KeySignal", back_populates="lead")
    status_history = relationship("LeadStatusHistory", back_populates="lead", order_by="LeadStatusHistory.created_at.desc()")
    assignment_history = relationship("RepAssignmentHistory", back_populates="lead", order_by="RepAssignmentHistory.created_at.desc()")
    event_logs = relationship("EventLog", back_populates="lead", order_by="EventLog.created_at.desc()")
    assigned_rep = relationship("SalesRep", foreign_keys=[assigned_rep_id])

    def is_active(self) -> bool:
        return self.status in {LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.NURTURING, LeadStatus.BOOKED}

