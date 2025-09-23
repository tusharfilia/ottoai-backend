"""
WebSocket endpoint for real-time communication.
"""
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.config import settings
from app.obs.logging import get_logger, extract_trace_id
from app.obs.tracing import get_tracer, add_span_attributes
from app.obs.metrics import metrics
from app.realtime.hub import ws_hub
from app.middleware.rate_limiter import RateLimiter

router = APIRouter()
logger = get_logger(__name__)
tracer = get_tracer(__name__)
security = HTTPBearer()

# Rate limiter for WebSocket control messages
ws_rate_limiter = RateLimiter()

async def authenticate_websocket(websocket: WebSocket) -> tuple[str, str, str]:
    """
    Authenticate WebSocket connection using Clerk JWT.
    
    Returns:
        tuple: (tenant_id, user_id, trace_id)
    
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Get authorization header
        headers = websocket.headers
        authorization = headers.get("authorization")
        
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        
        token = authorization[7:]  # Remove "Bearer " prefix
        
        # Verify JWT token (same logic as existing middleware)
        try:
            # For development, we'll use a simple validation
            # In production, this should verify against Clerk's JWKS
            payload = jwt.decode(
                token,
                options={"verify_signature": False}  # Skip signature verification for now
            )
            
            # Extract tenant and user information
            tenant_id = payload.get("org_id") or payload.get("organization_id")
            user_id = payload.get("sub") or payload.get("user_id")
            
            if not tenant_id or not user_id:
                raise HTTPException(status_code=401, detail="Invalid token payload")
            
            # Generate trace ID
            trace_id = extract_trace_id(websocket) if hasattr(websocket, 'headers') else None
            if not trace_id:
                import uuid
                trace_id = str(uuid.uuid4())
            
            return tenant_id, user_id, trace_id
            
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time communication.
    
    Clients must provide a valid JWT token in the Authorization header.
    After connection, clients can subscribe/unsubscribe to channels.
    """
    connection_id = None
    tenant_id = None
    user_id = None
    
    try:
        # Authenticate before accepting connection
        tenant_id, user_id, trace_id = await authenticate_websocket(websocket)
        
        # Accept WebSocket connection
        await websocket.accept()
        
        # Add connection to hub
        connection_id = await ws_hub.add_connection(
            websocket=websocket,
            tenant_id=tenant_id,
            user_id=user_id,
            trace_id=trace_id
        )
        
        # Update metrics
        metrics.set_active_connections(len(ws_hub.connections))
        
        # Log successful connection
        logger.info(
            "WebSocket connection established",
            extra={
                "connection_id": connection_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "trace_id": trace_id,
                "ip": websocket.client.host if websocket.client else None,
                "user_agent": websocket.headers.get("user-agent")
            }
        )
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "connection_id": connection_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "ts": asyncio.get_event_loop().time()
        }))
        
        # Message handling loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    
                    # Rate limit control messages
                    message_type = message.get("type")
                    if message_type in ["subscribe", "unsubscribe"]:
                        # Check rate limit for control messages
                        rate_limit_key = f"ws_control:{connection_id}"
                        allowed, retry_after = ws_rate_limiter._check_rate_limit(
                            rate_limit_key, "10/minute"
                        )
                        
                        if not allowed:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "error": "rate_limited",
                                "message": "Too many control messages",
                                "retry_after": retry_after,
                                "ts": asyncio.get_event_loop().time()
                            }))
                            continue
                    
                    # Handle message
                    await ws_hub.handle_client_message(connection_id, message)
                    
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "error": "invalid_json",
                        "message": "Invalid JSON format",
                        "ts": asyncio.get_event_loop().time()
                    }))
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": "server_error",
                    "message": "Internal server error",
                    "ts": asyncio.get_event_loop().time()
                }))
    
    except HTTPException as e:
        # Authentication failed
        logger.warning(f"WebSocket authentication failed: {e.detail}")
        await websocket.close(code=1008, reason=e.detail)
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during setup")
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    
    finally:
        # Clean up connection
        if connection_id:
            await ws_hub.remove_connection(connection_id)
            
            # Update metrics
            metrics.set_active_connections(len(ws_hub.connections))
            
            # Log disconnection
            logger.info(
                "WebSocket connection closed",
                extra={
                    "connection_id": connection_id,
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "remaining_connections": len(ws_hub.connections)
                }
            )


@router.get("/ws/test-emit")
async def test_emit_event(
    event: str = Query(..., description="Event name to emit"),
    tenant_id: str = Query(..., description="Tenant ID"),
    user_id: Optional[str] = Query(None, description="User ID"),
    lead_id: Optional[str] = Query(None, description="Lead ID"),
    dev_key: str = Query(None, alias="X-Dev-Key", description="Development key")
):
    """
    Test endpoint to emit events for WebSocket testing.
    Requires DEV_EMIT_KEY in production environments.
    """
    # Check if dev emit key is required and provided
    required_dev_key = getattr(settings, 'DEV_EMIT_KEY', None)
    
    if settings.ENVIRONMENT == "production" and not required_dev_key:
        raise HTTPException(status_code=404, detail="Not found")
    
    if required_dev_key and dev_key != required_dev_key:
        raise HTTPException(status_code=403, detail="Invalid development key")
    
    from app.realtime.bus import emit
    
    # Create test payload
    test_payload = {
        "message": f"Test event: {event}",
        "timestamp": asyncio.get_event_loop().time(),
        "test": True,
        "environment": settings.ENVIRONMENT
    }
    
    # Emit the event
    success = emit(
        event_name=event,
        payload=test_payload,
        tenant_id=tenant_id,
        user_id=user_id,
        lead_id=lead_id,
        severity="info"
    )
    
    return {
        "success": success,
        "event": event,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "lead_id": lead_id,
        "payload": test_payload,
        "environment": settings.ENVIRONMENT
    }


# Initialize WebSocket hub on startup
@router.on_event("startup")
async def startup_websocket_hub():
    """Start the WebSocket hub when the application starts."""
    await ws_hub.start()
    logger.info("WebSocket hub started")


@router.on_event("shutdown")
async def shutdown_websocket_hub():
    """Stop the WebSocket hub when the application shuts down."""
    await ws_hub.stop()
    logger.info("WebSocket hub stopped")
