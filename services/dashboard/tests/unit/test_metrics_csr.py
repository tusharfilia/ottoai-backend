"""
Unit tests for CSR metrics service.

Tests verify that CSRMetrics are computed correctly from Call, CallAnalysis, and Task data.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from uuid import uuid4

from app.models.call import Call
from app.models.call_analysis import CallAnalysis
from app.models.task import Task, TaskStatus, TaskAssignee
from app.models.enums import CallType, BookingStatus, CallOutcomeCategory
from app.services.metrics_service import MetricsService
from app.schemas.metrics import CSRMetrics


@pytest.fixture
def db_session():
    """Get database session for tests.
    
    Note: This fixture should be provided by conftest.py or pytest configuration.
    For now, tests will need a database session fixture to be available.
    """
    # In a real test setup, this would use a test database
    # For now, we'll assume the fixture is provided elsewhere
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def tenant_id():
    """Test tenant ID."""
    return "test_company_123"


@pytest.fixture
def csr_id():
    """Test CSR user ID."""
    return "test_csr_user_001"


@pytest.fixture
def date_range():
    """Test date range (last 30 days)."""
    end = datetime.utcnow()
    start = end - timedelta(days=30)
    return start, end


@pytest.fixture
def sample_calls(db_session, tenant_id, date_range):
    """Create sample Call records for testing."""
    start, end = date_range
    
    calls = []
    
    # Call 1: Qualified, booked
    call1 = Call(
        call_id=1,
        company_id=tenant_id,
        call_type=CallType.CSR_CALL.value,
        phone_number="+1234567890",
        name="Customer 1",
        created_at=start + timedelta(days=1)
    )
    db_session.add(call1)
    calls.append(call1)
    
    # Call 2: Qualified, not booked
    call2 = Call(
        call_id=2,
        company_id=tenant_id,
        call_type=CallType.CSR_CALL.value,
        phone_number="+1234567891",
        name="Customer 2",
        created_at=start + timedelta(days=2)
    )
    db_session.add(call2)
    calls.append(call2)
    
    # Call 3: Qualified, service not offered
    call3 = Call(
        call_id=3,
        company_id=tenant_id,
        call_type=CallType.CSR_CALL.value,
        phone_number="+1234567892",
        name="Customer 3",
        created_at=start + timedelta(days=3)
    )
    db_session.add(call3)
    calls.append(call3)
    
    # Call 4: Unqualified
    call4 = Call(
        call_id=4,
        company_id=tenant_id,
        call_type=CallType.CSR_CALL.value,
        phone_number="+1234567893",
        name="Customer 4",
        created_at=start + timedelta(days=4)
    )
    db_session.add(call4)
    calls.append(call4)
    
    # Call 5: Qualified, booked (with objections)
    call5 = Call(
        call_id=5,
        company_id=tenant_id,
        call_type=CallType.CSR_CALL.value,
        phone_number="+1234567894",
        name="Customer 5",
        created_at=start + timedelta(days=5)
    )
    db_session.add(call5)
    calls.append(call5)
    
    db_session.commit()
    return calls


@pytest.fixture
def sample_analyses(db_session, tenant_id, sample_calls):
    """Create sample CallAnalysis records for testing."""
    analyses = []
    
    # Analysis 1: Qualified (hot), booked
    analysis1 = CallAnalysis(
        id=str(uuid4()),
        call_id=1,
        tenant_id=tenant_id,
        uwc_job_id="job_1",
        lead_quality="hot",
        booking_status=BookingStatus.BOOKED.value,
        call_outcome_category=CallOutcomeCategory.QUALIFIED_AND_BOOKED.value,
        sop_compliance_score=9.0,
        objections=[],
        analyzed_at=datetime.utcnow()
    )
    db_session.add(analysis1)
    analyses.append(analysis1)
    
    # Analysis 2: Qualified (warm), not booked
    analysis2 = CallAnalysis(
        id=str(uuid4()),
        call_id=2,
        tenant_id=tenant_id,
        uwc_job_id="job_2",
        lead_quality="warm",
        booking_status=BookingStatus.NOT_BOOKED.value,
        call_outcome_category=CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value,
        sop_compliance_score=7.5,
        objections=["price"],
        analyzed_at=datetime.utcnow()
    )
    db_session.add(analysis2)
    analyses.append(analysis2)
    
    # Analysis 3: Qualified (cold), service not offered
    analysis3 = CallAnalysis(
        id=str(uuid4()),
        call_id=3,
        tenant_id=tenant_id,
        uwc_job_id="job_3",
        lead_quality="cold",
        booking_status=BookingStatus.SERVICE_NOT_OFFERED.value,
        call_outcome_category=CallOutcomeCategory.QUALIFIED_SERVICE_NOT_OFFERED.value,
        sop_compliance_score=8.0,
        objections=[],
        analyzed_at=datetime.utcnow()
    )
    db_session.add(analysis3)
    analyses.append(analysis3)
    
    # Analysis 4: Unqualified (no analysis or unqualified status)
    # This call has no analysis, so it won't be counted as qualified
    
    # Analysis 5: Qualified (hot), booked, with multiple objections
    analysis5 = CallAnalysis(
        id=str(uuid4()),
        call_id=5,
        tenant_id=tenant_id,
        uwc_job_id="job_5",
        lead_quality="hot",
        booking_status=BookingStatus.BOOKED.value,
        call_outcome_category=CallOutcomeCategory.QUALIFIED_AND_BOOKED.value,
        sop_compliance_score=9.5,
        objections=["price", "timeline", "competitor"],
        analyzed_at=datetime.utcnow()
    )
    db_session.add(analysis5)
    analyses.append(analysis5)
    
    db_session.commit()
    return analyses


@pytest.fixture
def sample_tasks(db_session, tenant_id, date_range):
    """Create sample Task records for testing."""
    now = datetime.utcnow()
    tasks = []
    
    # Task 1: Open, not overdue (due in future)
    task1 = Task(
        id=str(uuid4()),
        company_id=tenant_id,
        description="Follow up with Customer 1",
        assigned_to=TaskAssignee.CSR.value,
        status=TaskStatus.OPEN.value,
        due_at=now + timedelta(days=1)
    )
    db_session.add(task1)
    tasks.append(task1)
    
    # Task 2: Open, overdue
    task2 = Task(
        id=str(uuid4()),
        company_id=tenant_id,
        description="Call back Customer 2",
        assigned_to=TaskAssignee.CSR.value,
        status=TaskStatus.OPEN.value,
        due_at=now - timedelta(days=1)
    )
    db_session.add(task2)
    tasks.append(task2)
    
    # Task 3: Pending, not overdue
    task3 = Task(
        id=str(uuid4()),
        company_id=tenant_id,
        description="Send quote to Customer 3",
        assigned_to=TaskAssignee.CSR.value,
        status=TaskStatus.PENDING.value,
        due_at=now + timedelta(days=2)
    )
    db_session.add(task3)
    tasks.append(task3)
    
    # Task 4: Completed (should not be counted)
    task4 = Task(
        id=str(uuid4()),
        company_id=tenant_id,
        description="Completed task",
        assigned_to=TaskAssignee.CSR.value,
        status=TaskStatus.COMPLETED.value,
        due_at=now - timedelta(days=1)
    )
    db_session.add(task4)
    tasks.append(task4)
    
    # Task 5: Open, no due date (should be counted as open)
    task5 = Task(
        id=str(uuid4()),
        company_id=tenant_id,
        description="Task without due date",
        assigned_to=TaskAssignee.CSR.value,
        status=TaskStatus.OPEN.value,
        due_at=None
    )
    db_session.add(task5)
    tasks.append(task5)
    
    db_session.commit()
    return tasks


class TestCSRMetrics:
    """Test CSR overview metrics computation."""
    
    @pytest.mark.asyncio
    async def test_get_csr_overview_metrics_basic(
        self,
        db_session,
        tenant_id,
        csr_id,
        date_range,
        sample_calls,
        sample_analyses,
        sample_tasks
    ):
        """Test basic CSR metrics computation."""
        service = MetricsService(db_session)
        start, end = date_range
        
        metrics = await service.get_csr_overview_metrics(
            csr_id=csr_id,
            tenant_id=tenant_id,
            start=start,
            end=end
        )
        
        # Assert metrics
        assert isinstance(metrics, CSRMetrics)
        assert metrics.total_calls == 5  # All 5 calls
        
        # Qualified calls: calls 1, 2, 3, 5 (hot, warm, cold, hot)
        assert metrics.qualified_calls == 4
        
        # Qualified rate: 4/5 = 0.8
        assert metrics.qualified_rate == pytest.approx(0.8, abs=0.01)
        
        # Booked calls: calls 1, 5
        assert metrics.booked_calls == 2
        
        # Booking rate: 2/4 = 0.5
        assert metrics.booking_rate == pytest.approx(0.5, abs=0.01)
        
        # Service not offered: call 3
        assert metrics.service_not_offered_calls == 1
        
        # Service not offered rate: 1/4 = 0.25
        assert metrics.service_not_offered_rate == pytest.approx(0.25, abs=0.01)
        
        # Qualified but unbooked: call 2
        assert metrics.qualified_but_unbooked_calls == 1
        
        # Average objections: (0 + 1 + 0 + 3) / 4 = 1.0
        assert metrics.avg_objections_per_qualified_call == pytest.approx(1.0, abs=0.01)
        
        # Average compliance: (9.0 + 7.5 + 8.0 + 9.5) / 4 = 8.5
        assert metrics.avg_compliance_score == pytest.approx(8.5, abs=0.01)
        
        # Open followups: tasks 1, 3, 5 (not overdue)
        assert metrics.open_followups == 3
        
        # Overdue followups: task 2
        assert metrics.overdue_followups == 1
    
    @pytest.mark.asyncio
    async def test_get_csr_overview_metrics_no_calls(
        self,
        db_session,
        tenant_id,
        csr_id,
        date_range
    ):
        """Test metrics with no calls."""
        service = MetricsService(db_session)
        start, end = date_range
        
        metrics = await service.get_csr_overview_metrics(
            csr_id=csr_id,
            tenant_id=tenant_id,
            start=start,
            end=end
        )
        
        assert metrics.total_calls == 0
        assert metrics.qualified_calls == 0
        assert metrics.qualified_rate is None
        assert metrics.booked_calls == 0
        assert metrics.booking_rate is None
        assert metrics.service_not_offered_calls == 0
        assert metrics.service_not_offered_rate is None
        assert metrics.avg_objections_per_qualified_call is None
        assert metrics.qualified_but_unbooked_calls == 0
        assert metrics.avg_compliance_score is None
        assert metrics.open_followups == 0
        assert metrics.overdue_followups == 0
    
    @pytest.mark.asyncio
    async def test_get_csr_overview_metrics_no_qualified_calls(
        self,
        db_session,
        tenant_id,
        csr_id,
        date_range
    ):
        """Test metrics with calls but none qualified."""
        start, end = date_range
        
        # Create unqualified call
        call = Call(
            call_id=10,
            company_id=tenant_id,
            call_type=CallType.CSR_CALL.value,
            phone_number="+1234567899",
            name="Unqualified Customer",
            created_at=start + timedelta(days=1)
        )
        db_session.add(call)
        
        # Analysis with unqualified status
        analysis = CallAnalysis(
            id=str(uuid4()),
            call_id=10,
            tenant_id=tenant_id,
            uwc_job_id="job_unqualified",
            lead_quality="unqualified",
            analyzed_at=datetime.utcnow()
        )
        db_session.add(analysis)
        db_session.commit()
        
        service = MetricsService(db_session)
        metrics = await service.get_csr_overview_metrics(
            csr_id=csr_id,
            tenant_id=tenant_id,
            start=start,
            end=end
        )
        
        assert metrics.total_calls == 1
        assert metrics.qualified_calls == 0
        assert metrics.qualified_rate == pytest.approx(0.0, abs=0.01)
        assert metrics.booked_calls == 0
        assert metrics.booking_rate is None  # No qualified calls
        assert metrics.avg_objections_per_qualified_call is None
        assert metrics.avg_compliance_score is None
    
    @pytest.mark.asyncio
    async def test_get_csr_overview_metrics_date_filtering(
        self,
        db_session,
        tenant_id,
        csr_id,
        sample_calls,
        sample_analyses
    ):
        """Test that date filtering works correctly."""
        # Create a call outside the date range
        old_call = Call(
            call_id=99,
            company_id=tenant_id,
            call_type=CallType.CSR_CALL.value,
            phone_number="+1999999999",
            name="Old Customer",
            created_at=datetime.utcnow() - timedelta(days=60)  # 60 days ago
        )
        db_session.add(old_call)
        db_session.commit()
        
        # Query with date range that excludes old call
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        
        service = MetricsService(db_session)
        metrics = await service.get_csr_overview_metrics(
            csr_id=csr_id,
            tenant_id=tenant_id,
            start=start,
            end=end
        )
        
        # Should only include the 5 sample calls, not the old one
        assert metrics.total_calls == 5

