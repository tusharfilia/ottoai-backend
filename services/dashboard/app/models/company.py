from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from ..database import Base
from .service import Service
from datetime import datetime

class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True) 
    name = Column(String, unique=True, index=True)
    address = Column(String)
    phone_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # CallRail integration fields
    callrail_api_key = Column(String, nullable=True)
    callrail_account_id = Column(String, nullable=True)
    
    # Relationships
    calls = relationship("Call", back_populates="company")
    sales_reps = relationship("SalesRep", back_populates="company")
    sales_managers = relationship("SalesManager", back_populates="company")
    services = relationship("Service", back_populates="company")
    users = relationship("User", back_populates="company") 