from sqlalchemy import Column, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ..database import Base
#931980e753b188c6856ffaed726ef00a
class SalesRep(Base):
    __tablename__ = "sales_reps"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)  # This is now the Clerk user ID
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)  # Now references Clerk org ID
    manager_id = Column(String, ForeignKey("sales_managers.user_id"), nullable=True)  # Now references Clerk user ID
    active_geofences = Column(JSON, nullable=True)  # List of active geofences as (latitude, longitude, radius) tuples
    expo_push_token = Column(String, nullable=True)  # Expo Push Token for mobile notifications
    
    # Relationships
    calls = relationship("Call", back_populates="assigned_rep")
    manager = relationship("SalesManager", back_populates="sales_reps")
    company = relationship("Company", back_populates="sales_reps")
    user = relationship("User", back_populates="rep_profile")