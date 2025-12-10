"""
Unit tests to verify MetricsService invariants:
- Shunya is always the single source of truth for booking, qualification, objections, outcomes
- Never recompute or re-interpret Shunya fields
- Never infer booking from appointments
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.database import Base
from app.models.call import Call
from app.models.call_analysis import CallAnalysis
from app.models.appointment import Appointment, AppointmentStatus, AppointmentOutcome
from app.models.lead import Lead, LeadStatus, LeadSource
from app.models.contact_card import ContactCard
from app.models.company import Company
from app.models.enums import CallType, BookingStatus, CallOutcomeCategory
from app.services.metrics_service import MetricsService


@pytest.fixture(scope="function")
def test_db():
    """In-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(test_db: Session):
    """Provides a clean database session for each test."""
    return test_db


@pytest.fixture
def metrics_service(db_session: Session):
    """Provides a MetricsService instance."""
    return MetricsService(db_session)


@pytest.fixture
def setup_test_data(db_session: Session):
    """Sets up test data with company, contact card, and lead."""
    company_id = "test_company_1"
    csr_id = "test_csr_1"
    
    # Create company
    company = Company(id=company_id, name="Test Company")
    db_session.add(company)
    
    # Create contact card
    contact_card = ContactCard(
        id="contact_1",
        company_id=company_id,
        primary_phone="+1234567890",
        first_name="John",
        last_name="Doe"
    )
    db_session.add(contact_card)
    
    # Create lead
    lead = Lead(
        id="lead_1",
        company_id=company_id,
        contact_card_id=contact_card.id,
        status=LeadStatus.NEW
    )
    db_session.add(lead)
    
    db_session.commit()
    
    return company_id, csr_id, contact_card.id, lead.id


class TestShunyaBookingInvariants:
    """Test that booking is only determined by Shunya's booking_status."""
    
    @pytest.mark.asyncio
    async def test_booked_only_if_shunya_says_booked(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that calls are counted as booked ONLY if CallAnalysis.booking_status == 'booked'."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Call 1: Shunya says booked
        call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=1)
        )
        analysis1 = CallAnalysis(
            id="analysis1",
            call_id=1,
            tenant_id=company_id,
            uwc_job_id="job1",
            lead_quality="hot",
            booking_status=BookingStatus.BOOKED.value,  # Shunya says booked
            call_outcome_category=CallOutcomeCategory.QUALIFIED_AND_BOOKED.value,
            analyzed_at=now - timedelta(days=1)
        )
        
        # Call 2: Has appointment but Shunya says NOT booked
        call2 = Call(
            call_id=2,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=2)
        )
        analysis2 = CallAnalysis(
            id="analysis2",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job2",
            lead_quality="warm",
            booking_status=BookingStatus.NOT_BOOKED.value,  # Shunya says NOT booked
            call_outcome_category=CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value,
            analyzed_at=now - timedelta(days=2)
        )
        
        # Create appointment for call2 (should be ignored for booking semantics)
        appointment = Appointment(
            id="apt_1",
            company_id=company_id,
            lead_id=lead_id,
            contact_card_id=contact_card_id,
            scheduled_start=now + timedelta(days=1),
            status=AppointmentStatus.SCHEDULED.value
        )
        
        db_session.add_all([call1, analysis1, call2, analysis2, appointment])
        db_session.commit()
        
        # Get metrics
        metrics = await metrics_service.get_csr_overview_metrics(
            csr_user_id=csr_id,
            tenant_id=company_id,
            start=now - timedelta(days=10),
            end=now + timedelta(days=1)
        )
        
        # Should only count call1 as booked (Shunya says so)
        # Should NOT count call2 as booked even though it has an appointment
        assert metrics.booked_calls == 1
        assert metrics.qualified_calls == 2  # Both are qualified
        assert metrics.booking_rate == pytest.approx(1.0 / 2.0)  # 1 booked / 2 qualified
    
    @pytest.mark.asyncio
    async def test_qualified_only_if_shunya_says_qualified(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that calls are counted as qualified ONLY if CallAnalysis.lead_quality is hot/warm/cold/qualified."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Call 1: Shunya says qualified (hot)
        call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=1)
        )
        analysis1 = CallAnalysis(
            id="analysis1",
            call_id=1,
            tenant_id=company_id,
            uwc_job_id="job1",
            lead_quality="hot",  # Shunya says qualified
            booking_status=BookingStatus.NOT_BOOKED.value,
            analyzed_at=now - timedelta(days=1)
        )
        
        # Call 2: Shunya says unqualified
        call2 = Call(
            call_id=2,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=2)
        )
        analysis2 = CallAnalysis(
            id="analysis2",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job2",
            lead_quality="unqualified",  # Shunya says unqualified
            booking_status=BookingStatus.NOT_BOOKED.value,
            analyzed_at=now - timedelta(days=2)
        )
        
        # Call 3: No analysis (should not be counted as qualified)
        call3 = Call(
            call_id=3,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=3)
        )
        
        db_session.add_all([call1, analysis1, call2, analysis2, call3])
        db_session.commit()
        
        # Get metrics
        metrics = await metrics_service.get_csr_overview_metrics(
            csr_user_id=csr_id,
            tenant_id=company_id,
            start=now - timedelta(days=10),
            end=now + timedelta(days=1)
        )
        
        # Should only count call1 as qualified (Shunya says so)
        assert metrics.total_calls == 3
        assert metrics.qualified_calls == 1
        assert metrics.qualified_rate == pytest.approx(1.0 / 3.0)
    
    @pytest.mark.asyncio
    async def test_service_not_offered_only_if_shunya_says_so(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that service_not_offered is only counted if CallAnalysis.booking_status == 'service_not_offered'."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Call 1: Shunya says service_not_offered
        call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=1)
        )
        analysis1 = CallAnalysis(
            id="analysis1",
            call_id=1,
            tenant_id=company_id,
            uwc_job_id="job1",
            lead_quality="hot",
            booking_status=BookingStatus.SERVICE_NOT_OFFERED.value,  # Shunya says service_not_offered
            call_outcome_category=CallOutcomeCategory.QUALIFIED_SERVICE_NOT_OFFERED.value,
            analyzed_at=now - timedelta(days=1)
        )
        
        # Call 2: Shunya says not_booked (not service_not_offered)
        call2 = Call(
            call_id=2,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=2)
        )
        analysis2 = CallAnalysis(
            id="analysis2",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job2",
            lead_quality="warm",
            booking_status=BookingStatus.NOT_BOOKED.value,  # Shunya says not_booked (not service_not_offered)
            call_outcome_category=CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value,
            analyzed_at=now - timedelta(days=2)
        )
        
        db_session.add_all([call1, analysis1, call2, analysis2])
        db_session.commit()
        
        # Get metrics
        metrics = await metrics_service.get_csr_overview_metrics(
            csr_user_id=csr_id,
            tenant_id=company_id,
            start=now - timedelta(days=10),
            end=now + timedelta(days=1)
        )
        
        # Should only count call1 as service_not_offered
        assert metrics.service_not_offered_calls == 1
        assert metrics.qualified_calls == 2
        assert metrics.service_not_offered_rate == pytest.approx(1.0 / 2.0)
    
    @pytest.mark.asyncio
    async def test_qualified_but_unbooked_only_if_shunya_says_so(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that qualified_but_unbooked is only counted if CallAnalysis.call_outcome_category == 'qualified_but_unbooked'."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Call 1: Shunya says qualified_but_unbooked
        call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=1)
        )
        analysis1 = CallAnalysis(
            id="analysis1",
            call_id=1,
            tenant_id=company_id,
            uwc_job_id="job1",
            lead_quality="hot",
            booking_status=BookingStatus.NOT_BOOKED.value,
            call_outcome_category=CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value,  # Shunya says qualified_but_unbooked
            analyzed_at=now - timedelta(days=1)
        )
        
        # Call 2: Shunya says qualified_and_booked (not qualified_but_unbooked)
        call2 = Call(
            call_id=2,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=2)
        )
        analysis2 = CallAnalysis(
            id="analysis2",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job2",
            lead_quality="warm",
            booking_status=BookingStatus.BOOKED.value,
            call_outcome_category=CallOutcomeCategory.QUALIFIED_AND_BOOKED.value,  # Shunya says qualified_and_booked
            analyzed_at=now - timedelta(days=2)
        )
        
        db_session.add_all([call1, analysis1, call2, analysis2])
        db_session.commit()
        
        # Get metrics
        metrics = await metrics_service.get_csr_overview_metrics(
            csr_user_id=csr_id,
            tenant_id=company_id,
            start=now - timedelta(days=10),
            end=now + timedelta(days=1)
        )
        
        # Should only count call1 as qualified_but_unbooked
        assert metrics.qualified_but_unbooked_calls == 1
        assert metrics.qualified_calls == 2
    
    @pytest.mark.asyncio
    async def test_booking_trend_uses_shunya_not_appointments(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that booking trend uses CallAnalysis.booking_status, not appointments."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Call 1: Shunya says booked
        call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=1)
        )
        analysis1 = CallAnalysis(
            id="analysis1",
            call_id=1,
            tenant_id=company_id,
            uwc_job_id="job1",
            lead_quality="hot",
            booking_status=BookingStatus.BOOKED.value,  # Shunya says booked
            analyzed_at=now - timedelta(days=1)
        )
        
        # Call 2: Shunya says NOT booked, but has appointment (should be ignored)
        call2 = Call(
            call_id=2,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=2)
        )
        analysis2 = CallAnalysis(
            id="analysis2",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job2",
            lead_quality="warm",
            booking_status=BookingStatus.NOT_BOOKED.value,  # Shunya says NOT booked
            analyzed_at=now - timedelta(days=2)
        )
        
        # Create appointment for call2 (should be ignored)
        appointment = Appointment(
            id="apt_1",
            company_id=company_id,
            lead_id=lead_id,
            contact_card_id=contact_card_id,
            scheduled_start=now + timedelta(days=1),
            status=AppointmentStatus.SCHEDULED.value
        )
        
        db_session.add_all([call1, analysis1, call2, analysis2, appointment])
        db_session.commit()
        
        # Get booking trend
        trend = await metrics_service.get_csr_booking_trend(
            tenant_id=company_id,
            csr_user_id=csr_id,
            date_from=now - timedelta(days=10),
            date_to=now + timedelta(days=1),
            granularity="month"
        )
        
        # Should only count call1 as booked (from Shunya)
        # Should NOT count call2 even though it has an appointment
        assert len(trend.points) > 0
        latest_point = trend.points[-1]
        assert latest_point.total_leads == 2
        assert latest_point.qualified_leads == 2
        assert latest_point.booked_appointments == 1  # Only call1, not call2
        assert latest_point.booking_rate == pytest.approx(1.0 / 2.0)
    
    @pytest.mark.asyncio
    async def test_objections_only_from_shunya(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that objections are only counted from CallAnalysis.objections (Shunya field)."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Call 1: Shunya detected objections
        call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=1)
        )
        analysis1 = CallAnalysis(
            id="analysis1",
            call_id=1,
            tenant_id=company_id,
            uwc_job_id="job1",
            lead_quality="hot",
            booking_status=BookingStatus.NOT_BOOKED.value,
            objections=["price", "timeline"],  # Shunya detected 2 objections
            analyzed_at=now - timedelta(days=1)
        )
        
        # Call 2: Shunya detected no objections
        call2 = Call(
            call_id=2,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=2)
        )
        analysis2 = CallAnalysis(
            id="analysis2",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job2",
            lead_quality="warm",
            booking_status=BookingStatus.BOOKED.value,
            objections=[],  # Shunya detected no objections
            analyzed_at=now - timedelta(days=2)
        )
        
        db_session.add_all([call1, analysis1, call2, analysis2])
        db_session.commit()
        
        # Get metrics
        metrics = await metrics_service.get_csr_overview_metrics(
            csr_user_id=csr_id,
            tenant_id=company_id,
            start=now - timedelta(days=10),
            end=now + timedelta(days=1)
        )
        
        # Should count 2 objections total (only from call1, from Shunya)
        assert metrics.qualified_calls == 2
        assert metrics.avg_objections_per_qualified_call == pytest.approx(2.0 / 2.0)  # 2 objections / 2 qualified calls
    
    @pytest.mark.asyncio
    async def test_compliance_score_only_from_shunya(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that compliance scores are only from CallAnalysis.sop_compliance_score (Shunya field)."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Call 1: Shunya provided compliance score
        call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=1)
        )
        analysis1 = CallAnalysis(
            id="analysis1",
            call_id=1,
            tenant_id=company_id,
            uwc_job_id="job1",
            lead_quality="hot",
            booking_status=BookingStatus.BOOKED.value,
            sop_compliance_score=8.5,  # Shunya provided score
            analyzed_at=now - timedelta(days=1)
        )
        
        # Call 2: Shunya provided different compliance score
        call2 = Call(
            call_id=2,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=2)
        )
        analysis2 = CallAnalysis(
            id="analysis2",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job2",
            lead_quality="warm",
            booking_status=BookingStatus.NOT_BOOKED.value,
            sop_compliance_score=7.0,  # Shunya provided score
            analyzed_at=now - timedelta(days=2)
        )
        
        # Call 3: No compliance score from Shunya
        call3 = Call(
            call_id=3,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=3)
        )
        analysis3 = CallAnalysis(
            id="analysis3",
            call_id=3,
            tenant_id=company_id,
            uwc_job_id="job3",
            lead_quality="cold",
            booking_status=BookingStatus.NOT_BOOKED.value,
            sop_compliance_score=None,  # Shunya did not provide score
            analyzed_at=now - timedelta(days=3)
        )
        
        db_session.add_all([call1, analysis1, call2, analysis2, call3, analysis3])
        db_session.commit()
        
        # Get metrics
        metrics = await metrics_service.get_csr_overview_metrics(
            csr_user_id=csr_id,
            tenant_id=company_id,
            start=now - timedelta(days=10),
            end=now + timedelta(days=1)
        )
        
        # Should average only the scores from Shunya (8.5 and 7.0), not include call3
        assert metrics.avg_compliance_score == pytest.approx((8.5 + 7.0) / 2.0)
    
    @pytest.mark.asyncio
    async def test_missed_call_recovery_uses_shunya_not_appointments(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that missed call recovery uses CallAnalysis.booking_status, not appointments."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Missed call 1: Eventually got booked (Shunya says so in follow-up call)
        missed_call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            missed_call=True,
            created_at=now - timedelta(days=5)
        )
        
        # Follow-up call that got booked (Shunya says booked)
        followup_call1 = Call(
            call_id=2,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            missed_call=False,
            created_at=now - timedelta(days=4)
        )
        followup_analysis1 = CallAnalysis(
            id="analysis_followup1",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job_followup1",
            lead_quality="hot",
            booking_status=BookingStatus.BOOKED.value,  # Shunya says booked
            analyzed_at=now - timedelta(days=4)
        )
        
        # Missed call 2: Has appointment but Shunya says NOT booked (should not count as saved)
        missed_call2 = Call(
            call_id=3,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            missed_call=True,
            created_at=now - timedelta(days=3)
        )
        
        # Create appointment for missed_call2 (should be ignored)
        appointment = Appointment(
            id="apt_1",
            company_id=company_id,
            lead_id=lead_id,
            contact_card_id=contact_card_id,
            scheduled_start=now + timedelta(days=1),
            status=AppointmentStatus.SCHEDULED.value
        )
        
        db_session.add_all([
            missed_call1, followup_call1, followup_analysis1,
            missed_call2, appointment
        ])
        db_session.commit()
        
        # Get missed call recovery metrics
        recovery = await metrics_service.get_csr_missed_call_recovery(
            tenant_id=company_id,
            csr_user_id=csr_id,
            date_from=now - timedelta(days=10),
            date_to=now + timedelta(days=1)
        )
        
        # Should only count missed_call1 as saved (Shunya says followup_call1 was booked)
        # Should NOT count missed_call2 even though it has an appointment
        assert recovery.metrics.missed_calls_count == 2
        assert recovery.metrics.saved_calls_count == 1  # Only missed_call1 via followup_call1


class TestExecMetricsShunyaInvariants:
    """Test that exec metrics also use Shunya fields correctly."""
    
    @pytest.mark.asyncio
    async def test_exec_csr_metrics_uses_shunya_only(
        self,
        metrics_service: MetricsService,
        setup_test_data,
        db_session: Session
    ):
        """Test that exec CSR metrics use only Shunya fields."""
        company_id, csr_id, contact_card_id, lead_id = setup_test_data
        
        now = datetime.utcnow()
        
        # Call 1: Shunya says booked
        call1 = Call(
            call_id=1,
            company_id=company_id,
            owner_id=csr_id,
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=1)
        )
        analysis1 = CallAnalysis(
            id="analysis1",
            call_id=1,
            tenant_id=company_id,
            uwc_job_id="job1",
            lead_quality="hot",
            booking_status=BookingStatus.BOOKED.value,  # Shunya says booked
            call_outcome_category=CallOutcomeCategory.QUALIFIED_AND_BOOKED.value,
            objections=["price"],
            sop_compliance_score=8.5,
            sentiment_score=0.75,
            analyzed_at=now - timedelta(days=1)
        )
        
        # Call 2: Shunya says NOT booked (has appointment but should be ignored)
        call2 = Call(
            call_id=2,
            company_id=company_id,
            owner_id="other_csr",
            call_type=CallType.CSR_CALL.value,
            contact_card_id=contact_card_id,
            lead_id=lead_id,
            created_at=now - timedelta(days=2)
        )
        analysis2 = CallAnalysis(
            id="analysis2",
            call_id=2,
            tenant_id=company_id,
            uwc_job_id="job2",
            lead_quality="warm",
            booking_status=BookingStatus.NOT_BOOKED.value,  # Shunya says NOT booked
            call_outcome_category=CallOutcomeCategory.QUALIFIED_BUT_UNBOOKED.value,
            objections=[],
            sop_compliance_score=7.0,
            sentiment_score=0.65,
            analyzed_at=now - timedelta(days=2)
        )
        
        # Create appointment for call2 (should be ignored)
        appointment = Appointment(
            id="apt_1",
            company_id=company_id,
            lead_id=lead_id,
            contact_card_id=contact_card_id,
            scheduled_start=now + timedelta(days=1),
            status=AppointmentStatus.SCHEDULED.value
        )
        
        db_session.add_all([call1, analysis1, call2, analysis2, appointment])
        db_session.commit()
        
        # Get exec CSR metrics
        metrics = await metrics_service.get_exec_csr_metrics(
            tenant_id=company_id,
            date_from=now - timedelta(days=10),
            date_to=now + timedelta(days=1)
        )
        
        # Should only count call1 as booked (Shunya says so)
        # Should NOT count call2 even though it has an appointment
        assert metrics.total_calls == 2
        assert metrics.qualified_calls == 2
        assert metrics.booked_calls == 1  # Only call1
        assert metrics.booking_rate == pytest.approx(1.0 / 2.0)
        assert metrics.avg_objections_per_call == pytest.approx(1.0 / 2.0)  # 1 objection / 2 calls
        assert metrics.avg_compliance_score == pytest.approx((8.5 + 7.0) / 2.0)
        assert metrics.avg_sentiment_score == pytest.approx((0.75 + 0.65) / 2.0)

