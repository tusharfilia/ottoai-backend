"""
WebSocket hub for managing real-time connections and message distribution.
"""
import json
import time
import asyncio
import uuid
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis
from app.config import settings
from app.obs.logging import get_logger
from app.obs.metrics import record_cache_hit, record_cache_miss
from app.realtime.bus import event_bus

logger = get_logger(__name__)

# Configuration
HEARTBEAT_INTERVAL = 20  # Send ping every 20 seconds
HEARTBEAT_TIMEOUT = 40   # Disconnect if no pong within 40 seconds
MAX_QUEUE_SIZE = 100     # Maximum queued messages per connection

class WebSocketConnection:
    """Represents a single WebSocket connection with its state."""
    
    def __init__(
        self,
        websocket: WebSocket,
        connection_id: str,
        tenant_id: str,
        user_id: str,
        trace_id: str
    ):
        self.websocket = websocket
        self.connection_id = connection_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.trace_id = trace_id
        self.subscribed_channels: Set[str] = set()
        self.last_pong = time.time()
        self.message_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self.connected = True
        self.created_at = time.time()
    
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a message to the WebSocket client."""
        try:
            if not self.connected:
                return False
            
            # Check if queue is full
            if self.message_queue.full():
                # Drop oldest message and send buffer warning
                try:
                    self.message_queue.get_nowait()
                    await self.message_queue.put({
                        "type": "system",
                        "event": "system.buffer_dropped",
                        "ts": time.time(),
                        "data": {"reason": "Queue overflow", "max_size": MAX_QUEUE_SIZE}
                    })
                    logger.warning(
                        f"Message queue overflow for connection {self.connection_id}",
                        extra={
                            "connection_id": self.connection_id,
                            "tenant_id": self.tenant_id,
                            "user_id": self.user_id
                        }
                    )
                except asyncio.QueueEmpty:
                    pass
            
            # Add message to queue
            await self.message_queue.put(message)
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue message for connection {self.connection_id}: {e}")
            return False
    
    async def send_ping(self):
        """Send a ping message to the client."""
        await self.send_message({"type": "ping", "ts": time.time()})
    
    def handle_pong(self):
        """Handle pong response from client."""
        self.last_pong = time.time()
    
    def is_stale(self) -> bool:
        """Check if connection is stale (no pong within timeout)."""
        return time.time() - self.last_pong > HEARTBEAT_TIMEOUT
    
    def disconnect(self):
        """Mark connection as disconnected."""
        self.connected = False


class WebSocketHub:
    """Manages WebSocket connections and message distribution."""
    
    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self.channel_subscriptions: Dict[str, Set[str]] = {}  # channel -> set of connection_ids
        self._redis_pubsub = None
        self._pubsub_task = None
        self._heartbeat_task = None
        self._running = False
    
    async def start(self):
        """Start the WebSocket hub."""
        if self._running:
            return
        
        self._running = True
        
        # Set up Redis pub/sub
        if settings.REDIS_URL:
            try:
                redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                self._redis_pubsub = redis_client.pubsub()
                
                # Start pub/sub listener
                self._pubsub_task = asyncio.create_task(self._pubsub_listener())
                
                # Start heartbeat task
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                
                logger.info("WebSocket hub started with Redis pub/sub")
                
            except Exception as e:
                logger.error(f"Failed to start WebSocket hub with Redis: {e}")
                self._running = False
        else:
            logger.warning("No Redis URL configured - WebSocket hub running without pub/sub")
    
    async def stop(self):
        """Stop the WebSocket hub."""
        self._running = False
        
        # Cancel tasks
        if self._pubsub_task:
            self._pubsub_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        # Close Redis connection
        if self._redis_pubsub:
            await self._redis_pubsub.close()
        
        # Disconnect all connections
        for connection in list(self.connections.values()):
            await self._disconnect_connection(connection.connection_id)
        
        logger.info("WebSocket hub stopped")
    
    async def add_connection(
        self,
        websocket: WebSocket,
        tenant_id: str,
        user_id: str,
        trace_id: str
    ) -> str:
        """Add a new WebSocket connection."""
        connection_id = str(uuid.uuid4())
        
        connection = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
            tenant_id=tenant_id,
            user_id=user_id,
            trace_id=trace_id
        )
        
        self.connections[connection_id] = connection
        
        # Start message sender task for this connection
        asyncio.create_task(self._message_sender(connection))
        
        logger.info(
            f"WebSocket connection added: {connection_id}",
            extra={
                "connection_id": connection_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "trace_id": trace_id,
                "total_connections": len(self.connections)
            }
        )
        
        return connection_id
    
    async def remove_connection(self, connection_id: str):
        """Remove a WebSocket connection."""
        await self._disconnect_connection(connection_id)
    
    async def subscribe_to_channel(
        self,
        connection_id: str,
        channel: str
    ) -> bool:
        """Subscribe a connection to a channel."""
        connection = self.connections.get(connection_id)
        if not connection:
            return False
        
        # Validate channel access
        if not event_bus.validate_channel_access(channel, connection.tenant_id, connection.user_id):
            logger.warning(
                f"Channel access denied: {channel}",
                extra={
                    "connection_id": connection_id,
                    "channel": channel,
                    "tenant_id": connection.tenant_id,
                    "user_id": connection.user_id
                }
            )
            return False
        
        # Validate channel format
        if not event_bus.is_valid_channel_format(channel):
            logger.warning(
                f"Invalid channel format: {channel}",
                extra={"connection_id": connection_id, "channel": channel}
            )
            return False
        
        # Add to connection's subscriptions
        connection.subscribed_channels.add(channel)
        
        # Add to hub's channel mapping
        if channel not in self.channel_subscriptions:
            self.channel_subscriptions[channel] = set()
            # Subscribe to Redis channel
            if self._redis_pubsub:
                await self._redis_pubsub.subscribe(channel)
        
        self.channel_subscriptions[channel].add(connection_id)
        
        logger.info(
            f"Connection {connection_id} subscribed to {channel}",
            extra={
                "connection_id": connection_id,
                "channel": channel,
                "tenant_id": connection.tenant_id,
                "total_subscribers": len(self.channel_subscriptions[channel])
            }
        )
        
        return True
    
    async def unsubscribe_from_channel(
        self,
        connection_id: str,
        channel: str
    ) -> bool:
        """Unsubscribe a connection from a channel."""
        connection = self.connections.get(connection_id)
        if not connection:
            return False
        
        # Remove from connection's subscriptions
        connection.subscribed_channels.discard(channel)
        
        # Remove from hub's channel mapping
        if channel in self.channel_subscriptions:
            self.channel_subscriptions[channel].discard(connection_id)
            
            # If no more subscribers, unsubscribe from Redis
            if not self.channel_subscriptions[channel]:
                del self.channel_subscriptions[channel]
                if self._redis_pubsub:
                    await self._redis_pubsub.unsubscribe(channel)
        
        logger.info(
            f"Connection {connection_id} unsubscribed from {channel}",
            extra={
                "connection_id": connection_id,
                "channel": channel,
                "tenant_id": connection.tenant_id
            }
        )
        
        return True
    
    async def handle_client_message(
        self,
        connection_id: str,
        message: Dict[str, Any]
    ):
        """Handle a message from a WebSocket client."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        message_type = message.get("type")
        
        if message_type == "pong":
            connection.handle_pong()
            logger.debug(f"Pong received from connection {connection_id}")
            
        elif message_type == "subscribe":
            channel = message.get("channel")
            if channel:
                success = await self.subscribe_to_channel(connection_id, channel)
                await connection.send_message({
                    "type": "subscribe_result",
                    "channel": channel,
                    "success": success,
                    "ts": time.time()
                })
            
        elif message_type == "unsubscribe":
            channel = message.get("channel")
            if channel:
                success = await self.unsubscribe_from_channel(connection_id, channel)
                await connection.send_message({
                    "type": "unsubscribe_result",
                    "channel": channel,
                    "success": success,
                    "ts": time.time()
                })
        
        else:
            logger.warning(
                f"Unknown message type from connection {connection_id}: {message_type}",
                extra={"connection_id": connection_id, "message": message}
            )
    
    async def _disconnect_connection(self, connection_id: str):
        """Internal method to disconnect a connection."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        # Unsubscribe from all channels
        for channel in list(connection.subscribed_channels):
            await self.unsubscribe_from_channel(connection_id, channel)
        
        # Mark as disconnected
        connection.disconnect()
        
        # Remove from connections
        del self.connections[connection_id]
        
        logger.info(
            f"WebSocket connection removed: {connection_id}",
            extra={
                "connection_id": connection_id,
                "tenant_id": connection.tenant_id,
                "user_id": connection.user_id,
                "duration_seconds": time.time() - connection.created_at,
                "remaining_connections": len(self.connections)
            }
        )
    
    async def _pubsub_listener(self):
        """Listen for Redis pub/sub messages and distribute to WebSocket connections."""
        try:
            async for message in self._redis_pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    data = message["data"]
                    
                    try:
                        event_data = json.loads(data)
                        await self._distribute_message(channel, event_data)
                        record_cache_hit("pubsub_message")
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in pub/sub message: {e}")
                        record_cache_miss("pubsub_message")
                    except Exception as e:
                        logger.error(f"Error processing pub/sub message: {e}")
                        record_cache_miss("pubsub_message")
        
        except asyncio.CancelledError:
            logger.info("Pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"Pub/sub listener error: {e}")
    
    async def _distribute_message(self, channel: str, message: Dict[str, Any]):
        """Distribute a message to all subscribers of a channel."""
        if channel not in self.channel_subscriptions:
            return
        
        connection_ids = list(self.channel_subscriptions[channel])
        distributed_count = 0
        
        for connection_id in connection_ids:
            connection = self.connections.get(connection_id)
            if connection and connection.connected:
                success = await connection.send_message(message)
                if success:
                    distributed_count += 1
        
        logger.debug(
            f"Message distributed to {distributed_count}/{len(connection_ids)} connections on channel {channel}",
            extra={
                "channel": channel,
                "event": message.get("event"),
                "distributed": distributed_count,
                "total_subscribers": len(connection_ids)
            }
        )
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats and clean up stale connections."""
        try:
            while self._running:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                
                # Send pings and check for stale connections
                stale_connections = []
                
                for connection_id, connection in self.connections.items():
                    if connection.is_stale():
                        stale_connections.append(connection_id)
                    else:
                        await connection.send_ping()
                
                # Disconnect stale connections
                for connection_id in stale_connections:
                    logger.info(f"Disconnecting stale connection: {connection_id}")
                    await self._disconnect_connection(connection_id)
        
        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}")
    
    async def _message_sender(self, connection: WebSocketConnection):
        """Send queued messages to a WebSocket connection."""
        try:
            while connection.connected:
                try:
                    # Wait for a message with timeout
                    message = await asyncio.wait_for(
                        connection.message_queue.get(),
                        timeout=1.0
                    )
                    
                    # Send message to WebSocket
                    await connection.websocket.send_text(json.dumps(message))
                    
                except asyncio.TimeoutError:
                    # No message to send, continue loop
                    continue
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected: {connection.connection_id}")
                    break
                except Exception as e:
                    logger.error(f"Error sending message to {connection.connection_id}: {e}")
                    break
        
        except Exception as e:
            logger.error(f"Message sender error for {connection.connection_id}: {e}")
        finally:
            # Clean up connection
            await self._disconnect_connection(connection.connection_id)


# Global WebSocket hub instance
ws_hub = WebSocketHub()
