"""
Property Intelligence background tasks for scraping property data via OpenAI.
"""
import re
from datetime import datetime, timedelta
from typing import Dict, Optional

from celery import current_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.core.pii_masking import PIISafeLogger
from app.database import SessionLocal
from app.models.contact_card import ContactCard
from app.realtime.bus import emit

logger = PIISafeLogger(__name__)

# Property snapshot refresh threshold (30 days)
PROPERTY_SNAPSHOT_REFRESH_DAYS = 30


@celery_app.task(bind=True, max_retries=3)
def scrape_property_intelligence(self, contact_card_id: str):
    """
    Scrape property intelligence data from public sources using OpenAI Chat API.
    
    Args:
        contact_card_id: UUID of the ContactCard to update
        
    Returns:
        Dict with success status and details
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting property intelligence scrape for contact {contact_card_id}")
        
        # Fetch contact card
        contact = db.query(ContactCard).filter(ContactCard.id == contact_card_id).first()
        if not contact:
            logger.error(f"ContactCard {contact_card_id} not found")
            return {"success": False, "error": "ContactCard not found"}
        
        if not contact.address:
            logger.warning(f"ContactCard {contact_card_id} has no address - skipping scrape")
            return {"success": False, "error": "No address available"}
        
        if not contact.company_id:
            logger.error(f"ContactCard {contact_card_id} has no company_id")
            return {"success": False, "error": "No company_id"}
        
        # Check if scrape is needed (not already fresh)
        if contact.property_snapshot_updated_at:
            age_days = (datetime.utcnow() - contact.property_snapshot_updated_at).days
            if age_days < PROPERTY_SNAPSHOT_REFRESH_DAYS:
                logger.info(
                    f"Property snapshot for {contact_card_id} is fresh (age: {age_days} days) - skipping"
                )
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "Snapshot is fresh",
                    "age_days": age_days,
                }
        
        # Call OpenAI Chat API with multi-key support
        try:
            from app.services.openai_client_manager import get_openai_client_manager
            
            manager = get_openai_client_manager()
            
            if not manager.keys:
                logger.error(
                    f"No OpenAI API keys configured - cannot scrape property intelligence for contact {contact_card_id}"
                )
                return {
                    "success": False,
                    "error": "OpenAI API key not configured",
                    "contact_card_id": contact_card_id,
                }
            
            prompt = """You are a research assistant for a roofing company. Each time you are given an address, follow these instructions exactly:

Sources
Use only reliable public sources: county assessor, property portals (Zillow, Redfin, Realtor, Trulia, Homes.com), county GIS, HOA directories, and Google Maps/Street View.
Cross-check at least two sources whenever possible.
Do not guess.

Output Format
Return results as a single fenced bash code block.
No explanations, no extra commentary, no blank lines.

Formatting Rules
Each line must be formatted as Key="value".
Keys must be in Capitalized Case (e.g., Roof Type="Tile").
If a field is unknown, omit it completely (do not show at all).
Use Yes/No for boolean values.
Include commas in numbers (e.g., Last Sale Price="$310,000").
Keep values short and plain.

Required Fields (in this order)
Roof Type
Square Feet
Stories
Year Built
Access Notes (only if gated community)
Solar
HOA (Yes/No always included)
Subdivision
Last Sale Date
Last Sale Price
Est Value Range
Potential Equity = (Est Value Range – Last Sale Price)
Is this property for sale? Yes/No

Special Rules
Always prioritize roofing details (roof type, roofing material, replacement year if available).
Always calculate and include Potential Equity using today's value range minus the last sale price. Show it as a range like "$214,000 – $268,000". If equity is negative, show it with a minus sign.
Only include Access Notes when the property is in a gated community.
Exclude risks, listing status, zoning, garage parking, lot size, last roof work year, and HOA contact info.

After the Bash Block
Provide two lines:
Sources: followed by a comma-separated list of source names or links.
Google earth: Full url of this property in google earth

✅ This ensures every property report is uniform, concise, and focused on roofing, property size, value, HOA, and potential equity.

If the property is on the market say so and indicate that it is. if not say nothing.

Address: {address}"""

            # Execute with automatic key rotation and retry
            def make_request(client):
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a property research assistant that extracts structured data from public sources. Always return results in the exact format specified.",
                        },
                        {"role": "user", "content": prompt.format(address=contact.address)},
                    ],
                    temperature=0.1,
                )
                return response
            
            response = manager.execute_with_retry(make_request, max_retries=len(manager.keys) + 1)
            
            raw_response = response.choices[0].message.content
            logger.info(f"Received OpenAI response for contact {contact_card_id}")
            
        except Exception as e:
            logger.error(f"OpenAI API error for contact {contact_card_id}: {str(e)}")
            # Retry on transient errors (Celery will handle retries across different keys)
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)
        
        # Parse response
        try:
            parsed_data = _parse_property_response(raw_response)
            sources = parsed_data.get("sources", [])
            google_earth_url = parsed_data.get("google_earth_url")
            
            # Normalize property snapshot
            property_snapshot = parsed_data.get("snapshot", {})
            
            # Store on ContactCard
            contact.property_snapshot = property_snapshot
            contact.property_snapshot_raw = raw_response
            contact.property_snapshot_updated_at = datetime.utcnow()
            
            # Optionally store sources and google_earth_url in snapshot for easy access
            if sources or google_earth_url:
                if not contact.property_snapshot:
                    contact.property_snapshot = {}
                if sources:
                    contact.property_snapshot["_sources"] = sources
                if google_earth_url:
                    contact.property_snapshot["_google_earth_url"] = google_earth_url
            
            db.commit()
            db.refresh(contact)
            
            logger.info(
                f"Successfully updated property snapshot for contact {contact_card_id}",
                extra={"contact_id": contact_card_id, "company_id": contact.company_id},
            )
            
            # Emit event
            emit(
                event_name="contact.property_snapshot.updated",
                payload={
                    "contact_card_id": contact_card_id,
                    "company_id": contact.company_id,
                    "updated_at": contact.property_snapshot_updated_at.isoformat() + "Z",
                },
                tenant_id=contact.company_id,
                key=f"property_snapshot:{contact_card_id}",
            )
            
            return {
                "success": True,
                "contact_card_id": contact_card_id,
                "snapshot_keys": list(property_snapshot.keys()),
                "sources_count": len(sources),
            }
            
        except Exception as e:
            logger.error(
                f"Failed to parse property response for contact {contact_card_id}: {str(e)}",
                extra={"raw_response_preview": raw_response[:200] if raw_response else None},
            )
            # Store raw response even on parse failure
            contact.property_snapshot_raw = raw_response
            db.commit()
            return {
                "success": False,
                "error": "Parse failure",
                "details": str(e),
                "contact_card_id": contact_card_id,
            }
        
    except Exception as e:
        logger.error(f"Unexpected error in property intelligence scrape for {contact_card_id}: {str(e)}")
        raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)
    finally:
        db.close()


def _parse_property_response(response: str) -> Dict:
    """
    Parse OpenAI response containing fenced bash block and metadata.
    
    Expected format:
    ```bash
    Roof Type="Tile"
    Square Feet="2100"
    ...
    ```
    Sources: Zillow, County Assessor
    Google earth: https://earth.google.com/...
    
    Returns:
        Dict with 'snapshot' (normalized dict), 'sources' (list), 'google_earth_url' (str)
    """
    result = {"snapshot": {}, "sources": [], "google_earth_url": None}
    
    # Extract bash code block
    bash_match = re.search(r"```(?:bash)?\s*\n(.*?)\n```", response, re.DOTALL)
    if not bash_match:
        raise ValueError("No fenced bash block found in response")
    
    bash_content = bash_match.group(1)
    
    # Parse Key="value" pairs
    key_value_pattern = r'^([^=]+)="([^"]*)"$'
    for line in bash_content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        
        match = re.match(key_value_pattern, line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            
            # Normalize key to snake_case for storage
            normalized_key = _normalize_property_key(key)
            result["snapshot"][normalized_key] = value
    
    # Extract Sources line
    sources_match = re.search(r"Sources:\s*(.+?)(?:\n|$)", response, re.IGNORECASE)
    if sources_match:
        sources_str = sources_match.group(1).strip()
        result["sources"] = [s.strip() for s in sources_str.split(",")]
    
    # Extract Google earth URL
    google_match = re.search(r"Google earth:\s*(https?://[^\s]+)", response, re.IGNORECASE)
    if google_match:
        result["google_earth_url"] = google_match.group(1).strip()
    
    return result


def _normalize_property_key(key: str) -> str:
    """
    Normalize property key from "Capitalized Case" to snake_case.
    
    Examples:
        "Roof Type" -> "roof_type"
        "Square Feet" -> "square_feet"
        "Est Value Range" -> "est_value_range"
    """
    # Convert to lowercase and replace spaces with underscores
    normalized = key.lower().replace(" ", "_")
    
    # Handle special cases
    replacements = {
        "is_this_property_for_sale?": "is_for_sale",
        "potential_equity": "potential_equity",
    }
    
    for old, new in replacements.items():
        if old in normalized:
            normalized = normalized.replace(old, new)
    
    return normalized


def should_trigger_property_scrape(contact: ContactCard) -> bool:
    """
    Determine if property intelligence scrape should be triggered for a contact.
    
    Args:
        contact: ContactCard instance
        
    Returns:
        True if scrape should be triggered
    """
    if not contact.address:
        return False
    
    # If no snapshot exists, trigger
    if not contact.property_snapshot:
        return True
    
    # If snapshot is stale (older than threshold), trigger
    if not contact.property_snapshot_updated_at:
        return True
    
    age_days = (datetime.utcnow() - contact.property_snapshot_updated_at).days
    return age_days >= PROPERTY_SNAPSHOT_REFRESH_DAYS

