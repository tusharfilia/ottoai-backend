from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from ..database import Base
from datetime import datetime

class TranscriptAnalysis(Base):
    __tablename__ = "transcript_analyses"

    analysis_id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.call_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Detailed analysis data in JSON format
    greeting = Column(JSON, nullable=True)  # Greeting and introduction analysis
    customer_decision = Column(JSON, nullable=True)  # Customer engagement and outcome
    quoted_price = Column(JSON, nullable=True)  # Price and payment information
    company_mentions = Column(JSON, nullable=True)  # Company name mentions
    farewell = Column(JSON, nullable=True)  # Farewell and next steps
    
    # Specific information fields with actual quotes and timestamps
    rep_greeting_quote = Column(Text, nullable=True)
    rep_greeting_timestamp = Column(String, nullable=True)
    
    rep_introduction_quote = Column(Text, nullable=True)
    rep_introduction_timestamp = Column(String, nullable=True)
    
    company_mention_quote = Column(Text, nullable=True)
    company_mention_timestamp = Column(String, nullable=True)
    company_mention_count = Column(Integer, default=0)
    
    price_quote = Column(Text, nullable=True)
    price_quote_timestamp = Column(String, nullable=True)
    price_amount = Column(String, nullable=True)
    
    payment_discussion_quote = Column(Text, nullable=True)
    payment_discussion_timestamp = Column(String, nullable=True)
    
    discount_mention_quote = Column(Text, nullable=True)
    discount_mention_timestamp = Column(String, nullable=True)
    
    customer_decision_quote = Column(Text, nullable=True)
    customer_decision_timestamp = Column(String, nullable=True)
    customer_decision_status = Column(String, nullable=True)  # "bought", "deciding", "rejected"
    
    agreement_mention_quote = Column(Text, nullable=True)
    agreement_mention_timestamp = Column(String, nullable=True)
    
    goodbye_quote = Column(Text, nullable=True)
    goodbye_timestamp = Column(String, nullable=True)
    
    follow_up_quote = Column(Text, nullable=True)
    follow_up_timestamp = Column(String, nullable=True)
    follow_up_date = Column(String, nullable=True)
    
    document_sending_quote = Column(Text, nullable=True)
    document_sending_timestamp = Column(String, nullable=True)
    document_type = Column(String, nullable=True)
    
    paperwork_mention_quote = Column(Text, nullable=True)
    paperwork_mention_timestamp = Column(String, nullable=True)
    
    # Raw analysis result
    raw_analysis = Column(JSON, nullable=True)  # Store the complete raw analysis result
    
    # Metadata
    model_version = Column(String)  # LLM model used
    analysis_version = Column(Integer, default=1)  # Version number for multiple analyses
    
    # Relationship
    call = relationship("Call", backref="transcript_analyses") 