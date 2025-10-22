"""
Test data factories using factory_boy.
Simplifies test data creation with realistic, randomized values.

Usage:
    from tests.factories import CompanyFactory, UserFactory, CallFactory
    
    # Create test company
    company = CompanyFactory()
    
    # Create user in that company
    user = UserFactory(company=company, role='rep')
    
    # Create call assigned to that user
    call = CallFactory(company=company, assigned_rep=user)
"""
import factory
from factory import fuzzy
from datetime import datetime, timedelta
import random

from app.models.company import Company
from app.models.user import User
from app.models.sales_rep import SalesRep
from app.models.sales_manager import SalesManager
from app.models.call import Call
from app.models.call_transcript import CallTranscript
from app.models.call_analysis import CallAnalysis
from app.models.rag_document import RAGDocument, DocumentType, IndexingStatus
from app.models.rag_query import RAGQuery
from app.models.followup_draft import FollowUpDraft, DraftType, DraftStatus
from app.models.personal_clone_job import PersonalCloneJob, TrainingStatus, TrainingDataType


class CompanyFactory(factory.Factory):
    """Factory for creating test companies."""
    
    class Meta:
        model = Company
    
    id = factory.LazyFunction(lambda: f"company_{factory.Faker('uuid4').generate()}")
    name = factory.Faker('company')
    address = factory.Faker('address')
    phone_number = factory.Faker('phone_number')
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class UserFactory(factory.Factory):
    """Factory for creating test users."""
    
    class Meta:
        model = User
    
    id = factory.LazyFunction(lambda: f"user_{factory.Faker('uuid4').generate()}")
    email = factory.Faker('email')
    username = factory.Faker('user_name')
    name = factory.Faker('name')
    phone_number = factory.Faker('phone_number')
    role = fuzzy.FuzzyChoice(['exec', 'manager', 'csr', 'rep'])
    company = factory.SubFactory(CompanyFactory)
    company_id = factory.LazyAttribute(lambda obj: obj.company.id)


class SalesRepFactory(factory.Factory):
    """Factory for creating test sales reps."""
    
    class Meta:
        model = SalesRep
    
    user_id = factory.LazyFunction(lambda: f"rep_{factory.Faker('uuid4').generate()}")
    name = factory.Faker('name')
    phone_number = factory.Faker('phone_number')
    email = factory.Faker('email')
    company = factory.SubFactory(CompanyFactory)
    company_id = factory.LazyAttribute(lambda obj: obj.company.id)


class CallFactory(factory.Factory):
    """Factory for creating test calls."""
    
    class Meta:
        model = Call
    
    call_id = factory.Sequence(lambda n: n + 1000)
    name = factory.Faker('name')
    phone_number = factory.Faker('phone_number')
    address = factory.Faker('address')
    missed_call = fuzzy.FuzzyChoice([True, False])
    booked = fuzzy.FuzzyChoice([True, False])
    bought = fuzzy.FuzzyChoice([True, False, False])  # 33% won rate
    price_if_bought = factory.LazyAttribute(
        lambda obj: random.randint(15000, 50000) if obj.bought else None
    )
    transcript = factory.Faker('text', max_nb_chars=500)
    company = factory.SubFactory(CompanyFactory)
    company_id = factory.LazyAttribute(lambda obj: obj.company.id)
    created_at = factory.LazyFunction(lambda: datetime.utcnow() - timedelta(days=random.randint(0, 30)))
    updated_at = factory.LazyFunction(datetime.utcnow)


class CallTranscriptFactory(factory.Factory):
    """Factory for creating test call transcripts."""
    
    class Meta:
        model = CallTranscript
    
    id = factory.LazyFunction(lambda: f"transcript_{factory.Faker('uuid4').generate()}")
    call = factory.SubFactory(CallFactory)
    call_id = factory.LazyAttribute(lambda obj: obj.call.call_id)
    tenant_id = factory.LazyAttribute(lambda obj: obj.call.company_id)
    uwc_job_id = factory.LazyFunction(lambda: f"uwc_job_{factory.Faker('uuid4').generate()}")
    transcript_text = factory.Faker('text', max_nb_chars=1000)
    speaker_labels = factory.LazyFunction(lambda: [
        {"speaker": "rep", "text": "Hello, this is John from ABC Company", "start_time": 0.0, "end_time": 3.5},
        {"speaker": "customer", "text": "Hi, I need a quote for my roof", "start_time": 3.8, "end_time": 6.2}
    ])
    confidence_score = fuzzy.FuzzyFloat(0.85, 0.98)
    language = "en-US"
    word_count = fuzzy.FuzzyInteger(100, 500)
    processing_time_ms = fuzzy.FuzzyInteger(1000, 5000)
    created_at = factory.LazyFunction(datetime.utcnow)


class CallAnalysisFactory(factory.Factory):
    """Factory for creating test call analyses."""
    
    class Meta:
        model = CallAnalysis
    
    id = factory.LazyFunction(lambda: f"analysis_{factory.Faker('uuid4').generate()}")
    call = factory.SubFactory(CallFactory)
    call_id = factory.LazyAttribute(lambda obj: obj.call.call_id)
    tenant_id = factory.LazyAttribute(lambda obj: obj.call.company_id)
    uwc_job_id = factory.LazyFunction(lambda: f"uwc_analysis_{factory.Faker('uuid4').generate()}")
    objections = factory.LazyFunction(lambda: random.sample(
        ["price", "timeline", "need_to_think", "need_spouse_approval", "competitor"],
        k=random.randint(1, 3)
    ))
    objection_details = factory.LazyFunction(lambda: [
        {
            "type": "price",
            "timestamp": 120.5,
            "quote": "That's more expensive than I expected",
            "resolved": False
        }
    ])
    sentiment_score = fuzzy.FuzzyFloat(0.4, 0.9)
    engagement_score = fuzzy.FuzzyFloat(0.5, 0.95)
    coaching_tips = factory.LazyFunction(lambda: [
        {"tip": "Set agenda earlier", "priority": "high", "category": "sales_process"},
        {"tip": "Ask for sale before leaving", "priority": "medium", "category": "closing"}
    ])
    sop_stages_completed = factory.LazyFunction(lambda: ["connect", "agenda", "assess", "report"])
    sop_stages_missed = factory.LazyFunction(lambda: ["close", "referral"])
    sop_compliance_score = fuzzy.FuzzyFloat(5.0, 9.0)
    rehash_score = fuzzy.FuzzyFloat(3.0, 9.0)
    talk_time_ratio = fuzzy.FuzzyFloat(0.25, 0.45)
    lead_quality = fuzzy.FuzzyChoice(["qualified", "unqualified", "hot", "warm", "cold"])
    conversion_probability = fuzzy.FuzzyFloat(0.3, 0.9)
    analyzed_at = factory.LazyFunction(datetime.utcnow)
    created_at = factory.LazyFunction(datetime.utcnow)


class RAGDocumentFactory(factory.Factory):
    """Factory for creating test RAG documents."""
    
    class Meta:
        model = RAGDocument
    
    id = factory.LazyFunction(lambda: f"doc_{factory.Faker('uuid4').generate()}")
    tenant_id = factory.LazyFunction(lambda: f"company_{factory.Faker('uuid4').generate()}")
    uploaded_by = factory.LazyFunction(lambda: f"user_{factory.Faker('uuid4').generate()}")
    filename = factory.Faker('file_name', extension='pdf')
    file_url = factory.LazyAttribute(lambda obj: f"https://s3.amazonaws.com/otto-docs/{obj.tenant_id}/{obj.filename}")
    file_size_bytes = fuzzy.FuzzyInteger(10000, 5000000)
    content_type = "application/pdf"
    document_type = fuzzy.FuzzyChoice([t for t in DocumentType])
    indexing_status = fuzzy.FuzzyChoice([IndexingStatus.PENDING, IndexingStatus.INDEXED, IndexingStatus.PROCESSING])
    uwc_job_id = factory.LazyFunction(lambda: f"uwc_{factory.Faker('uuid4').generate()}")
    chunk_count = fuzzy.FuzzyInteger(5, 50)
    created_at = factory.LazyFunction(datetime.utcnow)


class RAGQueryFactory(factory.Factory):
    """Factory for creating test RAG queries."""
    
    class Meta:
        model = RAGQuery
    
    id = factory.LazyFunction(lambda: f"query_{factory.Faker('uuid4').generate()}")
    tenant_id = factory.LazyFunction(lambda: f"company_{factory.Faker('uuid4').generate()}")
    user_id = factory.LazyFunction(lambda: f"user_{factory.Faker('uuid4').generate()}")
    query_text = fuzzy.FuzzyChoice([
        "What are the most common objections?",
        "How can I improve my close rate?",
        "Show me calls with price objections",
        "What did Bradley do well in his last call?"
    ])
    answer_text = factory.Faker('text', max_nb_chars=500)
    citations = factory.LazyFunction(lambda: [
        {"doc_id": "doc_123", "filename": "script.pdf", "chunk_text": "...", "similarity_score": 0.92}
    ])
    confidence_score = fuzzy.FuzzyFloat(0.7, 0.95)
    result_count = fuzzy.FuzzyInteger(1, 10)
    latency_ms = fuzzy.FuzzyInteger(500, 3000)
    user_role = fuzzy.FuzzyChoice(['exec', 'manager', 'csr', 'rep'])
    created_at = factory.LazyFunction(datetime.utcnow)


class FollowUpDraftFactory(factory.Factory):
    """Factory for creating test follow-up drafts."""
    
    class Meta:
        model = FollowUpDraft
    
    id = factory.LazyFunction(lambda: f"draft_{factory.Faker('uuid4').generate()}")
    tenant_id = factory.LazyFunction(lambda: f"company_{factory.Faker('uuid4').generate()}")
    call = factory.SubFactory(CallFactory)
    call_id = factory.LazyAttribute(lambda obj: obj.call.call_id)
    generated_for = factory.LazyFunction(lambda: f"rep_{factory.Faker('uuid4').generate()}")
    generated_by = fuzzy.FuzzyChoice(["personal_clone", "generic_ai"])
    draft_text = factory.Faker('text', max_nb_chars=300)
    draft_type = fuzzy.FuzzyChoice([t for t in DraftType])
    tone = fuzzy.FuzzyChoice(["professional", "friendly", "urgent"])
    status = fuzzy.FuzzyChoice([DraftStatus.PENDING, DraftStatus.APPROVED])
    used = False
    blocked_by_quiet_hours = False
    created_at = factory.LazyFunction(datetime.utcnow)


class PersonalCloneJobFactory(factory.Factory):
    """Factory for creating test personal clone jobs."""
    
    class Meta:
        model = PersonalCloneJob
    
    id = factory.LazyFunction(lambda: f"job_{factory.Faker('uuid4').generate()}")
    tenant_id = factory.LazyFunction(lambda: f"company_{factory.Faker('uuid4').generate()}")
    rep_id = factory.LazyFunction(lambda: f"rep_{factory.Faker('uuid4').generate()}")
    training_data_type = fuzzy.FuzzyChoice([t for t in TrainingDataType])
    training_call_ids = factory.LazyFunction(lambda: [1001, 1002, 1003])
    training_media_urls = factory.LazyFunction(lambda: [
        "https://youtube.com/shorts/abc123",
        "https://tiktok.com/@user/video/xyz"
    ])
    total_media_count = 5
    uwc_job_id = factory.LazyFunction(lambda: f"uwc_training_{factory.Faker('uuid4').generate()}")
    status = fuzzy.FuzzyChoice([TrainingStatus.PENDING, TrainingStatus.PROCESSING, TrainingStatus.COMPLETED])
    progress_percent = fuzzy.FuzzyInteger(0, 100)
    created_at = factory.LazyFunction(datetime.utcnow)




