"""
MessageThread model for SMS/text message history linked to ContactCard.
Section 5.2 Tab 2, 6.2
"""
from datetime import datetime
import enum
from uuid import uuid4

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, Index, Boolean, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class MessageSenderRole(str, enum.Enum):
    """Who sent the message."""
    CUSTOMER = "customer"
    CSR = "csr"
    REP = "rep"
    MANAGER = "manager"
    OTTO = "otto"  # Otto automation
    SHUNYA = "shunya"  # Shunya/UWC automation


class MessageType(str, enum.Enum):
    """Type of message."""
    MANUAL = "manual"  # Human-sent
    AUTOMATED = "automated"  # AI/automation sent


class MessageDirection(str, enum.Enum):
    """Message direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageThread(Base):
    """
    SMS/text message history linked to ContactCard.
    
    Stores all messages (Otto auto, CSR→customer, customer→Otto AI, 
    appointment confirmations, reminders, voicemail transcripts).
    """
    __tablename__ = "message_threads"
    __table_args__ = (
        Index("ix_message_threads_contact_card", "contact_card_id"),
        Index("ix_message_threads_call", "call_id"),
        Index("ix_message_threads_company_created", "company_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    contact_card_id = Column(String, ForeignKey("contact_cards.id"), nullable=False, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=True, index=True, comment="Link to originating call if applicable")
    
    # Message content
    sender = Column(String, nullable=False, comment="Phone number or user ID of sender")
    sender_role = Column(Enum(MessageSenderRole, native_enum=False, name="message_sender_role"), nullable=False)
    body = Column(Text, nullable=False)
    
    # Message metadata
    message_type = Column(Enum(MessageType, native_enum=False, name="message_type"), nullable=False)
    direction = Column(Enum(MessageDirection, native_enum=False, name="message_direction"), nullable=False)
    
    # Provider details
    provider = Column(String, nullable=True, comment="Twilio, etc.")
    message_sid = Column(String, nullable=True, comment="Provider message ID")
    
    # Delivery tracking
    delivered = Column(Boolean, default=True)
    delivered_at = Column(DateTime, nullable=True)
    read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company")
    contact_card = relationship("ContactCard")
    call = relationship("Call")

