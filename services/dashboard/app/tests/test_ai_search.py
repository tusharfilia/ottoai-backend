"""
Tests for internal AI search endpoint.

Tests multi-tenant isolation, filtering, and aggregate calculations.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.call import Call
from app.models.call_analysis import CallAnalysis
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.models.company import Company
from app.models.sales_rep import SalesRep
from app.models.contact_card import ContactCard
from app.config import settings
import json

client = TestClient(app)

# Test data setup helpers
def create_test_company(db: Session, company_id: str) -> Company:
    """Create a test company."""
    company = Company(
        id=company_id,
        name=f"Test Company {company_id}",
        address="123 Test St",
    )
    db.add(company)
    db.commit()
    return company


def create_test_rep(db: Session, company_id: str, rep_id: str) -> SalesRep:
    """Create a test sales rep."""
    rep = SalesRep(
        user_id=rep_id,
        company_id=company_id,
    )
    db.add(rep)
    db.commit()
    return rep


def create_test_call(
    db: Session,
    company_id: str,
    rep_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    with_analysis: bool = False,
    objections: Optional[List[str]] = None,
    sentiment_score: Optional[float] = None,
    sop_score: Optional[float] = None,
) -> Call:
    """Create a test call with optional analysis."""
    call = Call(
        call_id=None,  # Auto-increment
        company_id=company_id,
        assigned_rep_id=rep_id,
        lead_id=lead_id,
        phone_number="+12025551234",
        created_at=created_at or datetime.utcnow(),
        last_call_duration=300,  # 5 minutes
    )
    db.add(call)
    db.flush()
    
    if with_analysis:
        analysis = CallAnalysis(
            id=f"analysis_{call.call_id}",
            call_id=call.call_id,
            tenant_id=company_id,
            uwc_job_id=f"job_{call.call_id}",
            objections=json.dumps(objections) if objections else None,
            sentiment_score=sentiment_score,
            sop_compliance_score=sop_score,
            analyzed_at=datetime.utcnow(),
        )
        db.add(analysis)
    
    db.commit()
    db.refresh(call)
    return call


def create_test_lead(
    db: Session,
    company_id: str,
    contact_card_id: str,
    status: str = "new",
) -> Lead:
    """Create a test lead."""
    lead = Lead(
        id=f"lead_{company_id}_{datetime.utcnow().timestamp()}",
        company_id=company_id,
        contact_card_id=contact_card_id,
        status=LeadStatus(status),
        source=LeadSource.INBOUND_CALL,
    )
    db.add(lead)
    db.commit()
    return lead


def create_test_appointment(
    db: Session,
    company_id: str,
    lead_id: str,
    rep_id: Optional[str] = None,
    outcome: str = "pending",
) -> Appointment:
    """Create a test appointment."""
    appointment = Appointment(
        id=f"apt_{company_id}_{datetime.utcnow().timestamp()}",
        company_id=company_id,
        lead_id=lead_id,
        assigned_rep_id=rep_id,
        scheduled_start=datetime.utcnow(),
        outcome=AppointmentOutcome(outcome),
        status=AppointmentStatus.SCHEDULED,
    )
    db.add(appointment)
    db.commit()
    return appointment


@pytest.fixture
def test_company_1(db: Session):
    """Create test company 1."""
    return create_test_company(db, "company_1")


@pytest.fixture
def test_company_2(db: Session):
    """Create test company 2."""
    return create_test_company(db, "company_2")


@pytest.fixture
def test_rep_1(db: Session, test_company_1):
    """Create test rep 1 for company 1."""
    return create_test_rep(db, test_company_1.id, "rep_1")


@pytest.fixture
def test_rep_2(db: Session, test_company_1):
    """Create test rep 2 for company 1."""
    return create_test_rep(db, test_company_1.id, "rep_2")


@pytest.fixture
def ai_internal_token():
    """Get AI internal token from settings."""
    return settings.AI_INTERNAL_TOKEN or "test_token"


class TestAISearchAuth:
    """Test authentication and tenant isolation."""
    
    def test_missing_token_returns_401(self):
        """Missing Authorization header returns 401."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={"X-Company-Id": "company_1"},
        )
        assert response.status_code == 401
    
    def test_invalid_token_returns_401(self):
        """Invalid token returns 401."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={
                "Authorization": "Bearer invalid_token",
                "X-Company-Id": "company_1",
            },
        )
        assert response.status_code == 401
    
    def test_missing_company_id_returns_400(self, ai_internal_token):
        """Missing X-Company-Id header returns 400."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={"Authorization": f"Bearer {ai_internal_token}"},
        )
        assert response.status_code == 400


class TestAISearchTenantIsolation:
    """Test multi-tenant data isolation."""
    
    def test_only_returns_company_data(
        self,
        db: Session,
        test_company_1,
        test_company_2,
        test_rep_1,
        ai_internal_token,
    ):
        """Search only returns data for authenticated company."""
        # Create calls for both companies
        call_1 = create_test_call(db, test_company_1.id, test_rep_1.user_id)
        call_2 = create_test_call(db, test_company_2.id, None)
        
        # Search as company_1
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        assert data["calls"][0]["call_id"] == call_1.call_id
        assert data["aggregates"]["total_calls"] == 1


class TestAISearchFilters:
    """Test various filter combinations."""
    
    def test_filter_by_rep_id(
        self,
        db: Session,
        test_company_1,
        test_rep_1,
        test_rep_2,
        ai_internal_token,
    ):
        """Filter by rep_id returns only that rep's calls."""
        # Create calls for both reps
        call_1 = create_test_call(db, test_company_1.id, test_rep_1.user_id)
        call_2 = create_test_call(db, test_company_1.id, test_rep_2.user_id)
        
        # Filter by rep_1
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"rep_ids": [test_rep_1.user_id]},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        assert data["calls"][0]["rep_id"] == test_rep_1.user_id
        assert data["aggregates"]["total_calls"] == 1
        assert data["aggregates"]["calls_by_rep"][test_rep_1.user_id] == 1
    
    def test_filter_by_date_range(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by date range returns only calls in that range."""
        now = datetime.utcnow()
        old_call = create_test_call(
            db, test_company_1.id, None, created_at=now - timedelta(days=60)
        )
        recent_call = create_test_call(
            db, test_company_1.id, None, created_at=now - timedelta(days=10)
        )
        
        # Filter last 30 days
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {
                    "date_from": (now - timedelta(days=30)).isoformat(),
                    "date_to": now.isoformat(),
                },
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert recent_call.call_id in call_ids
        assert old_call.call_id not in call_ids
    
    def test_filter_by_objections(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by has_objections returns only calls with objections."""
        call_with_obj = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["price", "timeline"],
        )
        call_without_obj = create_test_call(
            db, test_company_1.id, None, with_analysis=True, objections=None
        )
        
        # Filter by has_objections=True
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"has_objections": True},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_with_obj.call_id in call_ids
        assert call_without_obj.call_id not in call_ids
        assert data["aggregates"]["calls_with_objections"] == 1
    
    def test_filter_by_objection_labels(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by objection_labels returns only calls with those labels."""
        call_price = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["price"],
        )
        call_timeline = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["timeline"],
        )
        
        # Filter by objection_labels=["price"]
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"objection_labels": ["price"]},
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_price.call_id in call_ids
        assert call_timeline.call_id not in call_ids
    
    def test_filter_by_sentiment_range(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by sentiment range returns only calls in that range."""
        call_high = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            sentiment_score=0.8,
        )
        call_low = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            sentiment_score=0.3,
        )
        
        # Filter by sentiment_min=0.5
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"sentiment_min": 0.5},
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_high.call_id in call_ids
        assert call_low.call_id not in call_ids


class TestAISearchAggregates:
    """Test aggregate calculations."""
    
    def test_aggregates_calculation(
        self,
        db: Session,
        test_company_1,
        test_rep_1,
        test_rep_2,
        ai_internal_token,
    ):
        """Aggregates correctly calculate counts and distributions."""
        # Create calls with different outcomes and reps
        call_1 = create_test_call(
            db,
            test_company_1.id,
            test_rep_1.user_id,
            with_analysis=True,
            objections=["price"],
            sentiment_score=0.7,
        )
        call_2 = create_test_call(
            db,
            test_company_1.id,
            test_rep_2.user_id,
            with_analysis=True,
            objections=None,
            sentiment_score=0.5,
        )
        
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_aggregates": True, "include_calls": False},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        aggregates = data["aggregates"]
        
        assert aggregates["total_calls"] == 2
        assert aggregates["calls_by_rep"][test_rep_1.user_id] == 1
        assert aggregates["calls_by_rep"][test_rep_2.user_id] == 1
        assert aggregates["calls_with_objections"] == 1
        assert aggregates["objection_label_counts"]["price"] == 1
        assert aggregates["avg_sentiment"] is not None
        assert 0.5 <= aggregates["avg_sentiment"] <= 0.7


class TestAISearchOptions:
    """Test search options (include_calls, include_aggregates, pagination)."""
    
    def test_include_calls_false(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """When include_calls=False, calls list is empty."""
        create_test_call(db, test_company_1.id)
        
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": False, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 0
        assert data["aggregates"] is not None
    
    def test_pagination(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Pagination works correctly."""
        # Create 5 calls
        for i in range(5):
            create_test_call(db, test_company_1.id)
        
        # Get first page (limit=2)
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "limit": 2, "offset": 0},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 2
        
        # Get second page
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "limit": 2, "offset": 2},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 2



Tests multi-tenant isolation, filtering, and aggregate calculations.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.call import Call
from app.models.call_analysis import CallAnalysis
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.models.company import Company
from app.models.sales_rep import SalesRep
from app.models.contact_card import ContactCard
from app.config import settings
import json

client = TestClient(app)

# Test data setup helpers
def create_test_company(db: Session, company_id: str) -> Company:
    """Create a test company."""
    company = Company(
        id=company_id,
        name=f"Test Company {company_id}",
        address="123 Test St",
    )
    db.add(company)
    db.commit()
    return company


def create_test_rep(db: Session, company_id: str, rep_id: str) -> SalesRep:
    """Create a test sales rep."""
    rep = SalesRep(
        user_id=rep_id,
        company_id=company_id,
    )
    db.add(rep)
    db.commit()
    return rep


def create_test_call(
    db: Session,
    company_id: str,
    rep_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    with_analysis: bool = False,
    objections: Optional[List[str]] = None,
    sentiment_score: Optional[float] = None,
    sop_score: Optional[float] = None,
) -> Call:
    """Create a test call with optional analysis."""
    call = Call(
        call_id=None,  # Auto-increment
        company_id=company_id,
        assigned_rep_id=rep_id,
        lead_id=lead_id,
        phone_number="+12025551234",
        created_at=created_at or datetime.utcnow(),
        last_call_duration=300,  # 5 minutes
    )
    db.add(call)
    db.flush()
    
    if with_analysis:
        analysis = CallAnalysis(
            id=f"analysis_{call.call_id}",
            call_id=call.call_id,
            tenant_id=company_id,
            uwc_job_id=f"job_{call.call_id}",
            objections=json.dumps(objections) if objections else None,
            sentiment_score=sentiment_score,
            sop_compliance_score=sop_score,
            analyzed_at=datetime.utcnow(),
        )
        db.add(analysis)
    
    db.commit()
    db.refresh(call)
    return call


def create_test_lead(
    db: Session,
    company_id: str,
    contact_card_id: str,
    status: str = "new",
) -> Lead:
    """Create a test lead."""
    lead = Lead(
        id=f"lead_{company_id}_{datetime.utcnow().timestamp()}",
        company_id=company_id,
        contact_card_id=contact_card_id,
        status=LeadStatus(status),
        source=LeadSource.INBOUND_CALL,
    )
    db.add(lead)
    db.commit()
    return lead


def create_test_appointment(
    db: Session,
    company_id: str,
    lead_id: str,
    rep_id: Optional[str] = None,
    outcome: str = "pending",
) -> Appointment:
    """Create a test appointment."""
    appointment = Appointment(
        id=f"apt_{company_id}_{datetime.utcnow().timestamp()}",
        company_id=company_id,
        lead_id=lead_id,
        assigned_rep_id=rep_id,
        scheduled_start=datetime.utcnow(),
        outcome=AppointmentOutcome(outcome),
        status=AppointmentStatus.SCHEDULED,
    )
    db.add(appointment)
    db.commit()
    return appointment


@pytest.fixture
def test_company_1(db: Session):
    """Create test company 1."""
    return create_test_company(db, "company_1")


@pytest.fixture
def test_company_2(db: Session):
    """Create test company 2."""
    return create_test_company(db, "company_2")


@pytest.fixture
def test_rep_1(db: Session, test_company_1):
    """Create test rep 1 for company 1."""
    return create_test_rep(db, test_company_1.id, "rep_1")


@pytest.fixture
def test_rep_2(db: Session, test_company_1):
    """Create test rep 2 for company 1."""
    return create_test_rep(db, test_company_1.id, "rep_2")


@pytest.fixture
def ai_internal_token():
    """Get AI internal token from settings."""
    return settings.AI_INTERNAL_TOKEN or "test_token"


class TestAISearchAuth:
    """Test authentication and tenant isolation."""
    
    def test_missing_token_returns_401(self):
        """Missing Authorization header returns 401."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={"X-Company-Id": "company_1"},
        )
        assert response.status_code == 401
    
    def test_invalid_token_returns_401(self):
        """Invalid token returns 401."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={
                "Authorization": "Bearer invalid_token",
                "X-Company-Id": "company_1",
            },
        )
        assert response.status_code == 401
    
    def test_missing_company_id_returns_400(self, ai_internal_token):
        """Missing X-Company-Id header returns 400."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={"Authorization": f"Bearer {ai_internal_token}"},
        )
        assert response.status_code == 400


class TestAISearchTenantIsolation:
    """Test multi-tenant data isolation."""
    
    def test_only_returns_company_data(
        self,
        db: Session,
        test_company_1,
        test_company_2,
        test_rep_1,
        ai_internal_token,
    ):
        """Search only returns data for authenticated company."""
        # Create calls for both companies
        call_1 = create_test_call(db, test_company_1.id, test_rep_1.user_id)
        call_2 = create_test_call(db, test_company_2.id, None)
        
        # Search as company_1
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        assert data["calls"][0]["call_id"] == call_1.call_id
        assert data["aggregates"]["total_calls"] == 1


class TestAISearchFilters:
    """Test various filter combinations."""
    
    def test_filter_by_rep_id(
        self,
        db: Session,
        test_company_1,
        test_rep_1,
        test_rep_2,
        ai_internal_token,
    ):
        """Filter by rep_id returns only that rep's calls."""
        # Create calls for both reps
        call_1 = create_test_call(db, test_company_1.id, test_rep_1.user_id)
        call_2 = create_test_call(db, test_company_1.id, test_rep_2.user_id)
        
        # Filter by rep_1
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"rep_ids": [test_rep_1.user_id]},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        assert data["calls"][0]["rep_id"] == test_rep_1.user_id
        assert data["aggregates"]["total_calls"] == 1
        assert data["aggregates"]["calls_by_rep"][test_rep_1.user_id] == 1
    
    def test_filter_by_date_range(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by date range returns only calls in that range."""
        now = datetime.utcnow()
        old_call = create_test_call(
            db, test_company_1.id, None, created_at=now - timedelta(days=60)
        )
        recent_call = create_test_call(
            db, test_company_1.id, None, created_at=now - timedelta(days=10)
        )
        
        # Filter last 30 days
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {
                    "date_from": (now - timedelta(days=30)).isoformat(),
                    "date_to": now.isoformat(),
                },
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert recent_call.call_id in call_ids
        assert old_call.call_id not in call_ids
    
    def test_filter_by_objections(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by has_objections returns only calls with objections."""
        call_with_obj = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["price", "timeline"],
        )
        call_without_obj = create_test_call(
            db, test_company_1.id, None, with_analysis=True, objections=None
        )
        
        # Filter by has_objections=True
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"has_objections": True},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_with_obj.call_id in call_ids
        assert call_without_obj.call_id not in call_ids
        assert data["aggregates"]["calls_with_objections"] == 1
    
    def test_filter_by_objection_labels(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by objection_labels returns only calls with those labels."""
        call_price = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["price"],
        )
        call_timeline = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["timeline"],
        )
        
        # Filter by objection_labels=["price"]
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"objection_labels": ["price"]},
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_price.call_id in call_ids
        assert call_timeline.call_id not in call_ids
    
    def test_filter_by_sentiment_range(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by sentiment range returns only calls in that range."""
        call_high = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            sentiment_score=0.8,
        )
        call_low = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            sentiment_score=0.3,
        )
        
        # Filter by sentiment_min=0.5
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"sentiment_min": 0.5},
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_high.call_id in call_ids
        assert call_low.call_id not in call_ids


class TestAISearchAggregates:
    """Test aggregate calculations."""
    
    def test_aggregates_calculation(
        self,
        db: Session,
        test_company_1,
        test_rep_1,
        test_rep_2,
        ai_internal_token,
    ):
        """Aggregates correctly calculate counts and distributions."""
        # Create calls with different outcomes and reps
        call_1 = create_test_call(
            db,
            test_company_1.id,
            test_rep_1.user_id,
            with_analysis=True,
            objections=["price"],
            sentiment_score=0.7,
        )
        call_2 = create_test_call(
            db,
            test_company_1.id,
            test_rep_2.user_id,
            with_analysis=True,
            objections=None,
            sentiment_score=0.5,
        )
        
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_aggregates": True, "include_calls": False},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        aggregates = data["aggregates"]
        
        assert aggregates["total_calls"] == 2
        assert aggregates["calls_by_rep"][test_rep_1.user_id] == 1
        assert aggregates["calls_by_rep"][test_rep_2.user_id] == 1
        assert aggregates["calls_with_objections"] == 1
        assert aggregates["objection_label_counts"]["price"] == 1
        assert aggregates["avg_sentiment"] is not None
        assert 0.5 <= aggregates["avg_sentiment"] <= 0.7


class TestAISearchOptions:
    """Test search options (include_calls, include_aggregates, pagination)."""
    
    def test_include_calls_false(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """When include_calls=False, calls list is empty."""
        create_test_call(db, test_company_1.id)
        
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": False, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 0
        assert data["aggregates"] is not None
    
    def test_pagination(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Pagination works correctly."""
        # Create 5 calls
        for i in range(5):
            create_test_call(db, test_company_1.id)
        
        # Get first page (limit=2)
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "limit": 2, "offset": 0},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 2
        
        # Get second page
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "limit": 2, "offset": 2},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 2



Tests multi-tenant isolation, filtering, and aggregate calculations.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.call import Call
from app.models.call_analysis import CallAnalysis
from app.models.lead import Lead
from app.models.appointment import Appointment
from app.models.company import Company
from app.models.sales_rep import SalesRep
from app.models.contact_card import ContactCard
from app.config import settings
import json

client = TestClient(app)

# Test data setup helpers
def create_test_company(db: Session, company_id: str) -> Company:
    """Create a test company."""
    company = Company(
        id=company_id,
        name=f"Test Company {company_id}",
        address="123 Test St",
    )
    db.add(company)
    db.commit()
    return company


def create_test_rep(db: Session, company_id: str, rep_id: str) -> SalesRep:
    """Create a test sales rep."""
    rep = SalesRep(
        user_id=rep_id,
        company_id=company_id,
    )
    db.add(rep)
    db.commit()
    return rep


def create_test_call(
    db: Session,
    company_id: str,
    rep_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
    with_analysis: bool = False,
    objections: Optional[List[str]] = None,
    sentiment_score: Optional[float] = None,
    sop_score: Optional[float] = None,
) -> Call:
    """Create a test call with optional analysis."""
    call = Call(
        call_id=None,  # Auto-increment
        company_id=company_id,
        assigned_rep_id=rep_id,
        lead_id=lead_id,
        phone_number="+12025551234",
        created_at=created_at or datetime.utcnow(),
        last_call_duration=300,  # 5 minutes
    )
    db.add(call)
    db.flush()
    
    if with_analysis:
        analysis = CallAnalysis(
            id=f"analysis_{call.call_id}",
            call_id=call.call_id,
            tenant_id=company_id,
            uwc_job_id=f"job_{call.call_id}",
            objections=json.dumps(objections) if objections else None,
            sentiment_score=sentiment_score,
            sop_compliance_score=sop_score,
            analyzed_at=datetime.utcnow(),
        )
        db.add(analysis)
    
    db.commit()
    db.refresh(call)
    return call


def create_test_lead(
    db: Session,
    company_id: str,
    contact_card_id: str,
    status: str = "new",
) -> Lead:
    """Create a test lead."""
    lead = Lead(
        id=f"lead_{company_id}_{datetime.utcnow().timestamp()}",
        company_id=company_id,
        contact_card_id=contact_card_id,
        status=LeadStatus(status),
        source=LeadSource.INBOUND_CALL,
    )
    db.add(lead)
    db.commit()
    return lead


def create_test_appointment(
    db: Session,
    company_id: str,
    lead_id: str,
    rep_id: Optional[str] = None,
    outcome: str = "pending",
) -> Appointment:
    """Create a test appointment."""
    appointment = Appointment(
        id=f"apt_{company_id}_{datetime.utcnow().timestamp()}",
        company_id=company_id,
        lead_id=lead_id,
        assigned_rep_id=rep_id,
        scheduled_start=datetime.utcnow(),
        outcome=AppointmentOutcome(outcome),
        status=AppointmentStatus.SCHEDULED,
    )
    db.add(appointment)
    db.commit()
    return appointment


@pytest.fixture
def test_company_1(db: Session):
    """Create test company 1."""
    return create_test_company(db, "company_1")


@pytest.fixture
def test_company_2(db: Session):
    """Create test company 2."""
    return create_test_company(db, "company_2")


@pytest.fixture
def test_rep_1(db: Session, test_company_1):
    """Create test rep 1 for company 1."""
    return create_test_rep(db, test_company_1.id, "rep_1")


@pytest.fixture
def test_rep_2(db: Session, test_company_1):
    """Create test rep 2 for company 1."""
    return create_test_rep(db, test_company_1.id, "rep_2")


@pytest.fixture
def ai_internal_token():
    """Get AI internal token from settings."""
    return settings.AI_INTERNAL_TOKEN or "test_token"


class TestAISearchAuth:
    """Test authentication and tenant isolation."""
    
    def test_missing_token_returns_401(self):
        """Missing Authorization header returns 401."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={"X-Company-Id": "company_1"},
        )
        assert response.status_code == 401
    
    def test_invalid_token_returns_401(self):
        """Invalid token returns 401."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={
                "Authorization": "Bearer invalid_token",
                "X-Company-Id": "company_1",
            },
        )
        assert response.status_code == 401
    
    def test_missing_company_id_returns_400(self, ai_internal_token):
        """Missing X-Company-Id header returns 400."""
        response = client.post(
            "/internal/ai/search",
            json={"filters": {}, "options": {}},
            headers={"Authorization": f"Bearer {ai_internal_token}"},
        )
        assert response.status_code == 400


class TestAISearchTenantIsolation:
    """Test multi-tenant data isolation."""
    
    def test_only_returns_company_data(
        self,
        db: Session,
        test_company_1,
        test_company_2,
        test_rep_1,
        ai_internal_token,
    ):
        """Search only returns data for authenticated company."""
        # Create calls for both companies
        call_1 = create_test_call(db, test_company_1.id, test_rep_1.user_id)
        call_2 = create_test_call(db, test_company_2.id, None)
        
        # Search as company_1
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        assert data["calls"][0]["call_id"] == call_1.call_id
        assert data["aggregates"]["total_calls"] == 1


class TestAISearchFilters:
    """Test various filter combinations."""
    
    def test_filter_by_rep_id(
        self,
        db: Session,
        test_company_1,
        test_rep_1,
        test_rep_2,
        ai_internal_token,
    ):
        """Filter by rep_id returns only that rep's calls."""
        # Create calls for both reps
        call_1 = create_test_call(db, test_company_1.id, test_rep_1.user_id)
        call_2 = create_test_call(db, test_company_1.id, test_rep_2.user_id)
        
        # Filter by rep_1
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"rep_ids": [test_rep_1.user_id]},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 1
        assert data["calls"][0]["rep_id"] == test_rep_1.user_id
        assert data["aggregates"]["total_calls"] == 1
        assert data["aggregates"]["calls_by_rep"][test_rep_1.user_id] == 1
    
    def test_filter_by_date_range(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by date range returns only calls in that range."""
        now = datetime.utcnow()
        old_call = create_test_call(
            db, test_company_1.id, None, created_at=now - timedelta(days=60)
        )
        recent_call = create_test_call(
            db, test_company_1.id, None, created_at=now - timedelta(days=10)
        )
        
        # Filter last 30 days
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {
                    "date_from": (now - timedelta(days=30)).isoformat(),
                    "date_to": now.isoformat(),
                },
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert recent_call.call_id in call_ids
        assert old_call.call_id not in call_ids
    
    def test_filter_by_objections(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by has_objections returns only calls with objections."""
        call_with_obj = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["price", "timeline"],
        )
        call_without_obj = create_test_call(
            db, test_company_1.id, None, with_analysis=True, objections=None
        )
        
        # Filter by has_objections=True
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"has_objections": True},
                "options": {"include_calls": True, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_with_obj.call_id in call_ids
        assert call_without_obj.call_id not in call_ids
        assert data["aggregates"]["calls_with_objections"] == 1
    
    def test_filter_by_objection_labels(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by objection_labels returns only calls with those labels."""
        call_price = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["price"],
        )
        call_timeline = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            objections=["timeline"],
        )
        
        # Filter by objection_labels=["price"]
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"objection_labels": ["price"]},
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_price.call_id in call_ids
        assert call_timeline.call_id not in call_ids
    
    def test_filter_by_sentiment_range(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Filter by sentiment range returns only calls in that range."""
        call_high = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            sentiment_score=0.8,
        )
        call_low = create_test_call(
            db,
            test_company_1.id,
            None,
            with_analysis=True,
            sentiment_score=0.3,
        )
        
        # Filter by sentiment_min=0.5
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {"sentiment_min": 0.5},
                "options": {"include_calls": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        call_ids = [c["call_id"] for c in data["calls"]]
        assert call_high.call_id in call_ids
        assert call_low.call_id not in call_ids


class TestAISearchAggregates:
    """Test aggregate calculations."""
    
    def test_aggregates_calculation(
        self,
        db: Session,
        test_company_1,
        test_rep_1,
        test_rep_2,
        ai_internal_token,
    ):
        """Aggregates correctly calculate counts and distributions."""
        # Create calls with different outcomes and reps
        call_1 = create_test_call(
            db,
            test_company_1.id,
            test_rep_1.user_id,
            with_analysis=True,
            objections=["price"],
            sentiment_score=0.7,
        )
        call_2 = create_test_call(
            db,
            test_company_1.id,
            test_rep_2.user_id,
            with_analysis=True,
            objections=None,
            sentiment_score=0.5,
        )
        
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_aggregates": True, "include_calls": False},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        aggregates = data["aggregates"]
        
        assert aggregates["total_calls"] == 2
        assert aggregates["calls_by_rep"][test_rep_1.user_id] == 1
        assert aggregates["calls_by_rep"][test_rep_2.user_id] == 1
        assert aggregates["calls_with_objections"] == 1
        assert aggregates["objection_label_counts"]["price"] == 1
        assert aggregates["avg_sentiment"] is not None
        assert 0.5 <= aggregates["avg_sentiment"] <= 0.7


class TestAISearchOptions:
    """Test search options (include_calls, include_aggregates, pagination)."""
    
    def test_include_calls_false(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """When include_calls=False, calls list is empty."""
        create_test_call(db, test_company_1.id)
        
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": False, "include_aggregates": True},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 0
        assert data["aggregates"] is not None
    
    def test_pagination(
        self,
        db: Session,
        test_company_1,
        ai_internal_token,
    ):
        """Pagination works correctly."""
        # Create 5 calls
        for i in range(5):
            create_test_call(db, test_company_1.id)
        
        # Get first page (limit=2)
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "limit": 2, "offset": 0},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 2
        
        # Get second page
        response = client.post(
            "/internal/ai/search",
            json={
                "filters": {},
                "options": {"include_calls": True, "limit": 2, "offset": 2},
            },
            headers={
                "Authorization": f"Bearer {ai_internal_token}",
                "X-Company-Id": test_company_1.id,
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["calls"]) == 2

