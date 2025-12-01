from sqlalchemy import Column, String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from ..database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # This is now the Clerk user ID
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    name = Column(String)
    phone_number = Column(String, nullable=True)
    role = Column(String)  # "manager", "csr", "sales_rep"
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)  # Now references Clerk org ID
    territory = Column(String, nullable=True)  # For sales reps
    preferences_json = Column(JSON, nullable=True)  # User preferences stored as JSON
    
    # Relationships
    company = relationship("Company", back_populates="users")
    manager_profile = relationship("SalesManager", uselist=False, back_populates="user")
    rep_profile = relationship("SalesRep", uselist=False, back_populates="user")
    onboarding_events = relationship("OnboardingEvent", back_populates="user") 