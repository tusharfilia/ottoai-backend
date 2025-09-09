from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base
#931980e753b188c6856ffaed726ef00a
class SalesManager(Base):
    __tablename__ = "sales_managers"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)  # This is now the Clerk user ID
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)  # Now references Clerk org ID
    expo_push_token = Column(String, nullable=True)  # Expo Push Token for mobile notifications
    
    # Relationships
    sales_reps = relationship("SalesRep", back_populates="manager")
    company = relationship("Company", back_populates="sales_managers")
    user = relationship("User", back_populates="manager_profile") 