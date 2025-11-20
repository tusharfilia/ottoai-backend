"""
Tests for Property Intelligence pipeline.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.contact_card import ContactCard
from app.models.company import Company
from app.services.property_intelligence_service import maybe_trigger_property_scrape, update_contact_address
from app.tasks.property_intelligence_tasks import (
    scrape_property_intelligence,
    should_trigger_property_scrape,
    _parse_property_response,
)


@pytest.fixture
def contact_card_with_address(db_session: Session) -> ContactCard:
    """Create a contact card with an address for testing."""
    company = Company(id="test_company", name="Test Company", phone_number="+1234567890")
    db_session.add(company)
    db_session.commit()
    
    contact = ContactCard(
        id="test_contact",
        company_id="test_company",
        primary_phone="+15555555555",
        address="123 Main St, Anytown, CA 90210",
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


@pytest.fixture
def contact_card_with_stale_snapshot(db_session: Session) -> ContactCard:
    """Create a contact card with a stale property snapshot."""
    company = Company(id="test_company", name="Test Company", phone_number="+1234567890")
    db_session.add(company)
    db_session.commit()
    
    contact = ContactCard(
        id="test_contact_stale",
        company_id="test_company",
        primary_phone="+15555555556",
        address="456 Oak Ave, Anytown, CA 90210",
        property_snapshot={"roof_type": "Tile"},
        property_snapshot_updated_at=datetime.utcnow() - timedelta(days=31),  # Stale
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


@pytest.fixture
def contact_card_with_fresh_snapshot(db_session: Session) -> ContactCard:
    """Create a contact card with a fresh property snapshot."""
    company = Company(id="test_company", name="Test Company", phone_number="+1234567890")
    db_session.add(company)
    db_session.commit()
    
    contact = ContactCard(
        id="test_contact_fresh",
        company_id="test_company",
        primary_phone="+15555555557",
        address="789 Pine Rd, Anytown, CA 90210",
        property_snapshot={"roof_type": "Asphalt"},
        property_snapshot_updated_at=datetime.utcnow() - timedelta(days=15),  # Fresh
    )
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)
    return contact


class TestPropertyIntelligenceTrigger:
    """Test property intelligence scraping trigger logic."""
    
    def test_should_trigger_when_no_snapshot(self, contact_card_with_address: ContactCard):
        """Should trigger scrape when property_snapshot is None."""
        assert should_trigger_property_scrape(contact_card_with_address) is True
    
    def test_should_trigger_when_snapshot_stale(self, contact_card_with_stale_snapshot: ContactCard):
        """Should trigger scrape when property_snapshot is older than threshold."""
        assert should_trigger_property_scrape(contact_card_with_stale_snapshot) is True
    
    def test_should_not_trigger_when_snapshot_fresh(self, contact_card_with_fresh_snapshot: ContactCard):
        """Should not trigger scrape when property_snapshot is fresh."""
        assert should_trigger_property_scrape(contact_card_with_fresh_snapshot) is False
    
    def test_should_not_trigger_when_no_address(self, db_session: Session):
        """Should not trigger scrape when address is None."""
        company = Company(id="test_company", name="Test Company", phone_number="+1234567890")
        db_session.add(company)
        db_session.commit()
        
        contact = ContactCard(
            id="test_no_address",
            company_id="test_company",
            primary_phone="+15555555558",
            address=None,
        )
        db_session.add(contact)
        db_session.commit()
        db_session.refresh(contact)
        
        assert should_trigger_property_scrape(contact) is False
    
    @patch("app.services.property_intelligence_service.scrape_property_intelligence")
    def test_maybe_trigger_property_scrape_when_address_set(
        self, mock_scrape: MagicMock, db_session: Session, contact_card_with_address: ContactCard
    ):
        """Should enqueue scrape when address is set for the first time."""
        # Ensure contact has no snapshot
        contact_card_with_address.property_snapshot = None
        contact_card_with_address.property_snapshot_updated_at = None
        db_session.commit()
        db_session.refresh(contact_card_with_address)
        
        result = maybe_trigger_property_scrape(db_session, contact_card_with_address.id, previous_address=None)
        
        assert result is True
        mock_scrape.delay.assert_called_once_with(contact_card_with_address.id)
    
    @patch("app.services.property_intelligence_service.scrape_property_intelligence")
    def test_maybe_trigger_property_scrape_when_address_changed(
        self, mock_scrape: MagicMock, db_session: Session, contact_card_with_address: ContactCard
    ):
        """Should enqueue scrape when address changes."""
        # Set previous address
        previous_address = "100 Old St, Anytown, CA 90210"
        
        result = maybe_trigger_property_scrape(db_session, contact_card_with_address.id, previous_address=previous_address)
        
        assert result is True
        mock_scrape.delay.assert_called_once_with(contact_card_with_address.id)
    
    @patch("app.services.property_intelligence_service.scrape_property_intelligence")
    def test_maybe_trigger_property_scrape_when_snapshot_fresh(
        self, mock_scrape: MagicMock, db_session: Session, contact_card_with_fresh_snapshot: ContactCard
    ):
        """Should not enqueue scrape when snapshot is fresh."""
        previous_address = "100 Old St, Anytown, CA 90210"
        
        result = maybe_trigger_property_scrape(db_session, contact_card_with_fresh_snapshot.id, previous_address=previous_address)
        
        assert result is False
        mock_scrape.delay.assert_not_called()
    
    @patch("app.services.property_intelligence_service.scrape_property_intelligence")
    def test_maybe_trigger_property_scrape_when_address_unchanged(
        self, mock_scrape: MagicMock, db_session: Session, contact_card_with_address: ContactCard
    ):
        """Should not enqueue scrape when address hasn't changed."""
        previous_address = contact_card_with_address.address
        
        result = maybe_trigger_property_scrape(db_session, contact_card_with_address.id, previous_address=previous_address)
        
        assert result is False
        mock_scrape.delay.assert_not_called()


class TestPropertyIntelligenceScraper:
    """Test property intelligence scraper job."""
    
    @patch("app.tasks.property_intelligence_tasks.OpenAI")
    def test_scrape_property_intelligence_success(self, mock_openai: MagicMock, db_session: Session, contact_card_with_address: ContactCard):
        """Test successful property intelligence scrape."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '''```bash
Roof Type="Tile"
Square Feet="2100"
Stories="2"
Year Built="1998"
Access Notes="Guard gate, code required"
Solar="Yes"
HOA="Yes"
Subdivision="Cedar Ridge"
Last Sale Date="2021-06-15"
Last Sale Price="$310,000"
Est Value Range="$520,000 – $570,000"
Potential Equity="$210,000 – $260,000"
Is this property for sale?="No"
```
Sources: Zillow, County Assessor
Google earth: https://earth.google.com/web/@34.0522,-118.2437,100z
'''
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # Mock event bus
        with patch("app.tasks.property_intelligence_tasks.emit") as mock_emit:
            result = scrape_property_intelligence(contact_card_with_address.id)
        
        db_session.refresh(contact_card_with_address)
        
        assert result["success"] is True
        assert contact_card_with_address.property_snapshot is not None
        assert contact_card_with_address.property_snapshot["roof_type"] == "Tile"
        assert contact_card_with_address.property_snapshot["square_feet"] == "2100"
        assert contact_card_with_address.property_snapshot_updated_at is not None
        assert contact_card_with_address.property_snapshot_raw is not None
        
        # Verify event was emitted
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args.kwargs["event_name"] == "contact.property_snapshot.updated"
        assert call_args.kwargs["payload"]["contact_card_id"] == contact_card_with_address.id
    
    def test_scrape_property_intelligence_no_address(self, db_session: Session):
        """Test scrape fails when contact has no address."""
        company = Company(id="test_company", name="Test Company", phone_number="+1234567890")
        db_session.add(company)
        db_session.commit()
        
        contact = ContactCard(
            id="test_no_address",
            company_id="test_company",
            primary_phone="+15555555559",
            address=None,
        )
        db_session.add(contact)
        db_session.commit()
        db_session.refresh(contact)
        
        result = scrape_property_intelligence(contact.id)
        
        assert result["success"] is False
        assert "No address available" in result["error"]
    
    def test_scrape_property_intelligence_contact_not_found(self, db_session: Session):
        """Test scrape fails when contact doesn't exist."""
        result = scrape_property_intelligence("nonexistent_contact_id")
        
        assert result["success"] is False
        assert "not found" in result["error"]
    
    def test_parse_property_response(self):
        """Test parsing of OpenAI response."""
        response = '''```bash
Roof Type="Tile"
Square Feet="2100"
Stories="2"
Year Built="1998"
HOA="Yes"
Est Value Range="$520,000 – $570,000"
Potential Equity="$210,000 – $260,000"
```
Sources: Zillow, County Assessor
Google earth: https://earth.google.com/web/@34.0522,-118.2437,100z
'''
        
        parsed = _parse_property_response(response)
        
        assert parsed["snapshot"]["roof_type"] == "Tile"
        assert parsed["snapshot"]["square_feet"] == "2100"
        assert parsed["snapshot"]["stories"] == "2"
        assert parsed["snapshot"]["year_built"] == "1998"
        assert parsed["snapshot"]["hoa"] == "Yes"
        assert "Zillow" in parsed["sources"]
        assert "County Assessor" in parsed["sources"]
        assert "earth.google.com" in parsed["google_earth_url"]


class TestPropertyIntelligenceAPI:
    """Test property intelligence API endpoints."""
    
    def test_get_contact_card_with_property_intelligence(
        self, client, db_session: Session, contact_card_with_address: ContactCard
    ):
        """Test GET /api/v1/contact-cards/{id} returns property_intelligence."""
        # Set property snapshot
        contact_card_with_address.property_snapshot = {
            "roof_type": "Tile",
            "square_feet": "2100",
            "_sources": ["Zillow"],
            "_google_earth_url": "https://earth.google.com/web/@34.0522,-118.2437,100z",
        }
        contact_card_with_address.property_snapshot_updated_at = datetime.utcnow()
        db_session.commit()
        
        # Mock tenant context
        response = client.get(
            f"/api/v1/contact-cards/{contact_card_with_address.id}",
            headers={"X-Tenant-ID": contact_card_with_address.company_id},
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert "property_intelligence" in data
        assert data["property_intelligence"]["roof_type"] == "Tile"
        assert data["property_intelligence"]["square_feet"] == "2100"
        assert "Zillow" in data["property_intelligence"]["sources"]
        assert "earth.google.com" in data["property_intelligence"]["google_earth_url"]
    
    def test_get_contact_card_by_phone(
        self, client, db_session: Session, contact_card_with_address: ContactCard
    ):
        """Test GET /api/v1/contact-cards/by-phone returns contact card."""
        response = client.get(
            "/api/v1/contact-cards/by-phone",
            params={
                "company_id": contact_card_with_address.company_id,
                "phone_number": contact_card_with_address.primary_phone,
            },
            headers={"X-Tenant-ID": contact_card_with_address.company_id},
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == contact_card_with_address.id
        assert data["primary_phone"] == contact_card_with_address.primary_phone
    
    @patch("app.tasks.property_intelligence_tasks.scrape_property_intelligence")
    def test_refresh_property_intelligence(
        self, mock_scrape: MagicMock, client, db_session: Session, contact_card_with_address: ContactCard
    ):
        """Test POST /api/v1/contact-cards/{id}/refresh-property enqueues scrape."""
        response = client.post(
            f"/api/v1/contact-cards/{contact_card_with_address.id}/refresh-property",
            headers={"X-Tenant-ID": contact_card_with_address.company_id},
        )
        
        assert response.status_code == 202
        data = response.json()["data"]
        assert data["status"] == "queued"
        mock_scrape.delay.assert_called_once_with(contact_card_with_address.id)
    
    def test_refresh_property_intelligence_no_address(
        self, client, db_session: Session, contact_card_with_address: ContactCard
    ):
        """Test POST /api/v1/contact-cards/{id}/refresh-property fails when no address."""
        contact_card_with_address.address = None
        db_session.commit()
        
        response = client.post(
            f"/api/v1/contact-cards/{contact_card_with_address.id}/refresh-property",
            headers={"X-Tenant-ID": contact_card_with_address.company_id},
        )
        
        assert response.status_code == 400
        assert "no address" in response.json()["detail"].lower()

