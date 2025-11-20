from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ContactCard(Base):
    """
    Canonical representation of a customer within a tenant.
    Contact cards consolidate identifiers and support multiple leads/appointments.
    """

    __tablename__ = "contact_cards"

    __tablename__ = "contact_cards"
    __table_args__ = (
        UniqueConstraint("company_id", "primary_phone", name="uq_contact_cards_company_phone"),
        Index("ix_contact_cards_company_primary", "company_id", "primary_phone"),
        Index("ix_contact_cards_email", "company_id", "email"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)

    primary_phone = Column(String, nullable=False)
    secondary_phone = Column(String, nullable=True)
    email = Column(String, nullable=True)

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)

    custom_metadata = Column("metadata", JSON, nullable=True)
    property_snapshot = Column(JSON, nullable=True)
    property_snapshot_raw = Column(Text, nullable=True, description="Full original OpenAI response for property intelligence")
    property_snapshot_updated_at = Column(DateTime, nullable=True, description="Timestamp when property snapshot was last updated")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="contact_cards")
    leads = relationship("Lead", back_populates="contact_card", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="contact_card")
    calls = relationship("Call", back_populates="contact_card")
    tasks = relationship("Task", back_populates="contact_card")
    key_signals = relationship("KeySignal", back_populates="contact_card")
    event_logs = relationship("EventLog", back_populates="contact_card", order_by="EventLog.created_at.desc()")

    def full_name(self) -> Optional[str]:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name

