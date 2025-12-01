"""
Service for triggering property intelligence scraping when address changes.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.contact_card import ContactCard
from app.tasks.property_intelligence_tasks import (
    scrape_property_intelligence,
    should_trigger_property_scrape,
)
from app.core.pii_masking import PIISafeLogger

logger = PIISafeLogger(__name__)


def maybe_trigger_property_scrape(
    db: Session,
    contact_card_id: str,
    previous_address: Optional[str] = None,
) -> bool:
    """
    Check if property intelligence scrape should be triggered and enqueue if needed.
    
    This should be called after ContactCard.address is set or changed.
    
    Args:
        db: Database session
        contact_card_id: UUID of the ContactCard
        previous_address: Previous address value (if updating, not creating)
        
    Returns:
        True if scrape was enqueued, False otherwise
    """
    try:
        contact = db.query(ContactCard).filter(ContactCard.id == contact_card_id).first()
        if not contact:
            logger.warning(f"ContactCard {contact_card_id} not found for property scrape trigger")
            return False
        
        # Check if address was just set (was None, now has value)
        address_just_set = previous_address is None and contact.address is not None
        
        # Check if address changed
        address_changed = (
            previous_address is not None
            and contact.address is not None
            and previous_address != contact.address
        )
        
        # Only trigger if address was set/changed AND we should scrape
        if not (address_just_set or address_changed):
            return False
        
        if not should_trigger_property_scrape(contact):
            logger.info(
                f"Property snapshot for {contact_card_id} is fresh - skipping scrape",
                extra={"contact_id": contact_card_id, "company_id": contact.company_id},
            )
            return False
        
        # Enqueue scrape job
        scrape_property_intelligence.delay(contact_card_id)
        
        logger.info(
            f"Enqueued property intelligence scrape for contact {contact_card_id}",
            extra={
                "contact_id": contact_card_id,
                "company_id": contact.company_id,
                "address": contact.address,
                "trigger": "address_set" if address_just_set else "address_changed",
            },
        )
        
        return True
        
    except Exception as e:
        logger.error(
            f"Error triggering property scrape for contact {contact_card_id}: {str(e)}",
            extra={"contact_id": contact_card_id},
        )
        return False


def update_contact_address(
    db: Session,
    contact: ContactCard,
    new_address: Optional[str],
    city: Optional[str] = None,
    state: Optional[str] = None,
    postal_code: Optional[str] = None,
) -> bool:
    """
    Update contact address and trigger property scrape if needed.
    
    This is a convenience helper to ensure address updates always check for property scraping.
    
    Args:
        db: Database session
        contact: ContactCard instance
        new_address: New address value
        city: Optional city
        state: Optional state
        postal_code: Optional postal code
        
    Returns:
        True if property scrape was triggered
    """
    previous_address = contact.address
    contact.address = new_address
    if city:
        contact.city = city
    if state:
        contact.state = state
    if postal_code:
        contact.postal_code = postal_code
    
    db.commit()
    db.refresh(contact)
    
    # Trigger scrape if address was set/changed
    return maybe_trigger_property_scrape(db, contact.id, previous_address)




