"""
Task model for tracking action items across calls, appointments, and automation.
Section 3.5 - Tasks system.
"""
from datetime import datetime
import enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, Boolean, Index, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class TaskSource(str, enum.Enum):
    """Source of task creation."""
    OTTO = "otto"  # Otto automation/AI
    SHUNYA = "shunya"  # Shunya/UWC AI
    MANUAL = "manual"  # Human-created


class TaskAssignee(str, enum.Enum):
    """Who the task is assigned to."""
    CSR = "csr"  # Customer Service Rep
    REP = "rep"  # Sales Rep
    MANAGER = "manager"  # Manager
    AI = "ai"  # AI/Otto automation


class TaskStatus(str, enum.Enum):
    """Task status."""
    OPEN = "open"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Task(Base):
    """
    Task/action item linked to ContactCard, Lead, Appointment, or Call.
    
    Examples:
    - "Follow up at 5pm"
    - "Customer deciding with spouse"
    - "Send contract"
    - "Request for photos"
    """
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_contact_card", "contact_card_id"),
        Index("ix_tasks_lead", "lead_id"),
        Index("ix_tasks_appointment", "appointment_id"),
        Index("ix_tasks_assigned_to", "assigned_to"),
        Index("ix_tasks_status_due", "status", "due_at"),
        Index("ix_tasks_unique_key", "unique_key", "company_id"),  # For idempotency checks
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Foreign keys (nullable - task can be linked to multiple entities)
    contact_card_id = Column(String, ForeignKey("contact_cards.id"), nullable=True, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), nullable=True, index=True)
    appointment_id = Column(String, ForeignKey("appointments.id"), nullable=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=True, index=True)
    
    # Task details
    description = Column(Text, nullable=False, comment="Task description")
    assigned_to = Column(
        Enum(TaskAssignee, native_enum=False, name="task_assignee"),
        nullable=False,
        comment="Who should complete this task"
    )
    source = Column(
        Enum(TaskSource, native_enum=False, name="task_source"),
        nullable=False,
        comment="How this task was created"
    )
    
    # Idempotency: natural key for duplicate detection
    unique_key = Column(String, nullable=True, index=True, comment="Hash of (source, description, contact_card_id) for duplicate detection")
    
    # Scheduling
    due_at = Column(DateTime, nullable=True, index=True, comment="When task is due")
    status = Column(
        Enum(TaskStatus, native_enum=False, name="task_status"),
        nullable=False,
        default=TaskStatus.OPEN,
        index=True,
    )
    
    # Completion tracking
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(String, nullable=True, comment="User ID who completed the task")
    
    # Metadata
    priority = Column(String, nullable=True, comment="high/medium/low")
    metadata = Column(Text, nullable=True, comment="Additional context as JSON")
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    contact_card = relationship("ContactCard", back_populates="tasks")
    lead = relationship("Lead", back_populates="tasks")
    appointment = relationship("Appointment", back_populates="tasks")
    company = relationship("Company", foreign_keys=[company_id])
