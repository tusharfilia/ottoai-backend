from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime
import enum

class CallType(str, enum.Enum):
    SALES_FOLLOWUP = "sales_followup"
    HOMEOWNER_FOLLOWUP = "homeowner_followup"

class ScheduledCall(Base):
    __tablename__ = "scheduled_calls"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, ForeignKey("calls.call_id"))
    company_id = Column(String, ForeignKey("companies.id"))
    scheduled_time = Column(DateTime, nullable=False)
    call_type = Column(String, nullable=False)
    status = Column(String)  # blank, completed, failed
    is_completed = Column(Boolean, default=False)  # New dedicated completion flag
    bland_call_id = Column(String, nullable=True)  # Store Bland.ai call ID after making call
    created_at = Column(DateTime, default=datetime.utcnow)

    call = relationship("Call", backref="scheduled_calls")
    company = relationship("Company", backref="scheduled_calls")