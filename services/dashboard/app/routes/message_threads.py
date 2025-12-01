"""
Message thread (SMS) read endpoints.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.message_thread import MessageThread, MessageDirection, MessageSenderRole
from app.models.contact_card import ContactCard
from app.models.call import Call
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response

router = APIRouter(prefix="/api/v1/message-threads", tags=["message-threads"])


class MessageItem(BaseModel):
    """Single message in a thread."""
    id: str = Field(..., description="Message ID")
    sender: str = Field(..., description="Sender phone number or user ID")
    sender_role: str = Field(..., description="Sender role")
    body: str = Field(..., description="Message body")
    direction: str = Field(..., description="Message direction (inbound/outbound)")
    created_at: datetime = Field(..., description="When message was sent")
    provider: Optional[str] = Field(None, description="Provider (Twilio, etc.)")
    message_sid: Optional[str] = Field(None, description="Provider message ID")
    delivered: bool = Field(True, description="Whether message was delivered")
    read: bool = Field(False, description="Whether message was read")
    
    class Config:
        from_attributes = True


class MessageThreadResponse(BaseModel):
    """Response for message thread."""
    contact_card_id: str = Field(..., description="Contact card ID")
    messages: List[MessageItem] = Field(default_factory=list, description="List of messages in chronological order")
    total: int = Field(..., description="Total message count")


@router.get("/{contact_card_id}", response_model=APIResponse[MessageThreadResponse])
@require_role("manager", "csr", "sales_rep")
async def get_message_thread(
    request: Request,
    contact_card_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db),
) -> APIResponse[MessageThreadResponse]:
    """
    Get message thread (SMS/nurture) for a contact card.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Verify contact card exists and belongs to tenant
    contact_card = db.query(ContactCard).filter(
        ContactCard.id == contact_card_id,
        ContactCard.company_id == tenant_id
    ).first()
    
    if not contact_card:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Contact card not found",
                details={"contact_card_id": contact_card_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Query MessageThread records with pagination
    threads_query = db.query(MessageThread).filter(
        MessageThread.contact_card_id == contact_card_id,
        MessageThread.company_id == tenant_id
    )
    total_count = threads_query.count()
    threads = threads_query.order_by(MessageThread.created_at.asc()).offset(offset).limit(limit).all()
    
    # Build message items
    message_items = []
    for thread in threads:
        message_items.append(MessageItem(
            id=thread.id,
            sender=thread.sender,
            sender_role=thread.sender_role.value,
            body=thread.body,
            direction=thread.direction.value,
            created_at=thread.created_at,
            provider=thread.provider,
            message_sid=thread.message_sid,
            delivered=thread.delivered,
            read=thread.read,
        ))
    
    # Fallback: If no MessageThread records, try to extract from Call.text_messages
    if not message_items:
        calls = db.query(Call).filter(
            Call.contact_card_id == contact_card_id,
            Call.company_id == tenant_id,
            Call.text_messages.isnot(None)
        ).order_by(Call.created_at.asc()).all()
        
        import json
        for call in calls:
            try:
                text_messages = json.loads(call.text_messages) if isinstance(call.text_messages, str) else call.text_messages
                if isinstance(text_messages, list):
                    for msg in text_messages:
                        message_items.append(MessageItem(
                            id=f"call_{call.call_id}_{msg.get('timestamp', '')}",
                            sender=msg.get("from", call.phone_number or "unknown"),
                            sender_role="customer" if msg.get("direction") == "inbound" else "csr",
                            body=msg.get("message", ""),
                            direction=msg.get("direction", "inbound"),
                            created_at=datetime.fromisoformat(msg.get("timestamp", call.created_at.isoformat())) if isinstance(msg.get("timestamp"), str) else call.created_at,
                            provider=msg.get("provider", "unknown"),
                            message_sid=msg.get("message_sid"),
                            delivered=True,
                            read=False,
                        ))
            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip invalid JSON
                continue
    
    response = MessageThreadResponse(
        contact_card_id=contact_card_id,
        messages=message_items,
        total=total_count,  # Use total_count from query, not len(message_items) which is paginated
    )
    
    return APIResponse(data=response)


"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.message_thread import MessageThread, MessageDirection, MessageSenderRole
from app.models.contact_card import ContactCard
from app.models.call import Call
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response

router = APIRouter(prefix="/api/v1/message-threads", tags=["message-threads"])


class MessageItem(BaseModel):
    """Single message in a thread."""
    id: str = Field(..., description="Message ID")
    sender: str = Field(..., description="Sender phone number or user ID")
    sender_role: str = Field(..., description="Sender role")
    body: str = Field(..., description="Message body")
    direction: str = Field(..., description="Message direction (inbound/outbound)")
    created_at: datetime = Field(..., description="When message was sent")
    provider: Optional[str] = Field(None, description="Provider (Twilio, etc.)")
    message_sid: Optional[str] = Field(None, description="Provider message ID")
    delivered: bool = Field(True, description="Whether message was delivered")
    read: bool = Field(False, description="Whether message was read")
    
    class Config:
        from_attributes = True


class MessageThreadResponse(BaseModel):
    """Response for message thread."""
    contact_card_id: str = Field(..., description="Contact card ID")
    messages: List[MessageItem] = Field(default_factory=list, description="List of messages in chronological order")
    total: int = Field(..., description="Total message count")


@router.get("/{contact_card_id}", response_model=APIResponse[MessageThreadResponse])
@require_role("manager", "csr", "sales_rep")
async def get_message_thread(
    request: Request,
    contact_card_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db),
) -> APIResponse[MessageThreadResponse]:
    """
    Get message thread (SMS/nurture) for a contact card.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Verify contact card exists and belongs to tenant
    contact_card = db.query(ContactCard).filter(
        ContactCard.id == contact_card_id,
        ContactCard.company_id == tenant_id
    ).first()
    
    if not contact_card:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Contact card not found",
                details={"contact_card_id": contact_card_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Query MessageThread records with pagination
    threads_query = db.query(MessageThread).filter(
        MessageThread.contact_card_id == contact_card_id,
        MessageThread.company_id == tenant_id
    )
    total_count = threads_query.count()
    threads = threads_query.order_by(MessageThread.created_at.asc()).offset(offset).limit(limit).all()
    
    # Build message items
    message_items = []
    for thread in threads:
        message_items.append(MessageItem(
            id=thread.id,
            sender=thread.sender,
            sender_role=thread.sender_role.value,
            body=thread.body,
            direction=thread.direction.value,
            created_at=thread.created_at,
            provider=thread.provider,
            message_sid=thread.message_sid,
            delivered=thread.delivered,
            read=thread.read,
        ))
    
    # Fallback: If no MessageThread records, try to extract from Call.text_messages
    if not message_items:
        calls = db.query(Call).filter(
            Call.contact_card_id == contact_card_id,
            Call.company_id == tenant_id,
            Call.text_messages.isnot(None)
        ).order_by(Call.created_at.asc()).all()
        
        import json
        for call in calls:
            try:
                text_messages = json.loads(call.text_messages) if isinstance(call.text_messages, str) else call.text_messages
                if isinstance(text_messages, list):
                    for msg in text_messages:
                        message_items.append(MessageItem(
                            id=f"call_{call.call_id}_{msg.get('timestamp', '')}",
                            sender=msg.get("from", call.phone_number or "unknown"),
                            sender_role="customer" if msg.get("direction") == "inbound" else "csr",
                            body=msg.get("message", ""),
                            direction=msg.get("direction", "inbound"),
                            created_at=datetime.fromisoformat(msg.get("timestamp", call.created_at.isoformat())) if isinstance(msg.get("timestamp"), str) else call.created_at,
                            provider=msg.get("provider", "unknown"),
                            message_sid=msg.get("message_sid"),
                            delivered=True,
                            read=False,
                        ))
            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip invalid JSON
                continue
    
    response = MessageThreadResponse(
        contact_card_id=contact_card_id,
        messages=message_items,
        total=total_count,  # Use total_count from query, not len(message_items) which is paginated
    )
    
    return APIResponse(data=response)


"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.message_thread import MessageThread, MessageDirection, MessageSenderRole
from app.models.contact_card import ContactCard
from app.models.call import Call
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response

router = APIRouter(prefix="/api/v1/message-threads", tags=["message-threads"])


class MessageItem(BaseModel):
    """Single message in a thread."""
    id: str = Field(..., description="Message ID")
    sender: str = Field(..., description="Sender phone number or user ID")
    sender_role: str = Field(..., description="Sender role")
    body: str = Field(..., description="Message body")
    direction: str = Field(..., description="Message direction (inbound/outbound)")
    created_at: datetime = Field(..., description="When message was sent")
    provider: Optional[str] = Field(None, description="Provider (Twilio, etc.)")
    message_sid: Optional[str] = Field(None, description="Provider message ID")
    delivered: bool = Field(True, description="Whether message was delivered")
    read: bool = Field(False, description="Whether message was read")
    
    class Config:
        from_attributes = True


class MessageThreadResponse(BaseModel):
    """Response for message thread."""
    contact_card_id: str = Field(..., description="Contact card ID")
    messages: List[MessageItem] = Field(default_factory=list, description="List of messages in chronological order")
    total: int = Field(..., description="Total message count")


@router.get("/{contact_card_id}", response_model=APIResponse[MessageThreadResponse])
@require_role("manager", "csr", "sales_rep")
async def get_message_thread(
    request: Request,
    contact_card_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    db: Session = Depends(get_db),
) -> APIResponse[MessageThreadResponse]:
    """
    Get message thread (SMS/nurture) for a contact card.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Verify contact card exists and belongs to tenant
    contact_card = db.query(ContactCard).filter(
        ContactCard.id == contact_card_id,
        ContactCard.company_id == tenant_id
    ).first()
    
    if not contact_card:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Contact card not found",
                details={"contact_card_id": contact_card_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Query MessageThread records with pagination
    threads_query = db.query(MessageThread).filter(
        MessageThread.contact_card_id == contact_card_id,
        MessageThread.company_id == tenant_id
    )
    total_count = threads_query.count()
    threads = threads_query.order_by(MessageThread.created_at.asc()).offset(offset).limit(limit).all()
    
    # Build message items
    message_items = []
    for thread in threads:
        message_items.append(MessageItem(
            id=thread.id,
            sender=thread.sender,
            sender_role=thread.sender_role.value,
            body=thread.body,
            direction=thread.direction.value,
            created_at=thread.created_at,
            provider=thread.provider,
            message_sid=thread.message_sid,
            delivered=thread.delivered,
            read=thread.read,
        ))
    
    # Fallback: If no MessageThread records, try to extract from Call.text_messages
    if not message_items:
        calls = db.query(Call).filter(
            Call.contact_card_id == contact_card_id,
            Call.company_id == tenant_id,
            Call.text_messages.isnot(None)
        ).order_by(Call.created_at.asc()).all()
        
        import json
        for call in calls:
            try:
                text_messages = json.loads(call.text_messages) if isinstance(call.text_messages, str) else call.text_messages
                if isinstance(text_messages, list):
                    for msg in text_messages:
                        message_items.append(MessageItem(
                            id=f"call_{call.call_id}_{msg.get('timestamp', '')}",
                            sender=msg.get("from", call.phone_number or "unknown"),
                            sender_role="customer" if msg.get("direction") == "inbound" else "csr",
                            body=msg.get("message", ""),
                            direction=msg.get("direction", "inbound"),
                            created_at=datetime.fromisoformat(msg.get("timestamp", call.created_at.isoformat())) if isinstance(msg.get("timestamp"), str) else call.created_at,
                            provider=msg.get("provider", "unknown"),
                            message_sid=msg.get("message_sid"),
                            delivered=True,
                            read=False,
                        ))
            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip invalid JSON
                continue
    
    response = MessageThreadResponse(
        contact_card_id=contact_card_id,
        messages=message_items,
        total=total_count,  # Use total_count from query, not len(message_items) which is paginated
    )
    
    return APIResponse(data=response)

