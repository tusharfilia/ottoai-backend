"""
Webhook Idempotency Service

Prevents duplicate processing from provider retries by maintaining
idempotency keys in the database with proper transaction handling.
"""
import logging
import os
from typing import Callable, Any, Tuple, Dict
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)

# Metrics counters (would integrate with Prometheus in production)
webhook_processed_total = 0
webhook_duplicates_total = 0
webhook_failures_total = 0
webhook_idempotency_purged_total = 0


def with_idempotency(
    provider: str, 
    external_id: str, 
    tenant_id: str, 
    process_fn: Callable[[], Any],
    trace_id: str = None
) -> Tuple[Dict[str, Any], int]:
    """
    Execute a webhook handler with idempotency protection.
    
    Args:
        provider: Provider name ("callrail", "twilio", "clerk")
        external_id: Stable external identifier from webhook payload
        tenant_id: Tenant ID from middleware
        process_fn: Function to execute for first-time processing
        trace_id: Optional trace ID for logging
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    db = next(get_db())
    
    try:
        # Start transaction
        db.begin()
        
        # Try to insert new idempotency key
        insert_query = text("""
            INSERT INTO idempotency_keys (tenant_id, provider, external_id, last_seen_at, attempts)
            VALUES (:tenant_id, :provider, :external_id, NOW(), 1)
            ON CONFLICT (tenant_id, provider, external_id)
            DO UPDATE SET 
                last_seen_at = NOW(),
                attempts = idempotency_keys.attempts + 1
            RETURNING first_processed_at, (xmax = 0) as was_inserted
        """)
        
        result = db.execute(insert_query, {
            'tenant_id': tenant_id,
            'provider': provider,
            'external_id': external_id
        }).fetchone()
        
        # Check if this was a first-time insert
        was_first_time = result.was_inserted if hasattr(result, 'was_inserted') else result[1]
        first_processed_at = result.first_processed_at if hasattr(result, 'first_processed_at') else result[0]
        
        if not was_first_time and first_processed_at is not None:
            # Duplicate delivery - already processed
            logger.info(
                "Webhook duplicate ignored",
                extra={
                    'trace_id': trace_id,
                    'tenant_id': tenant_id,
                    'provider': provider,
                    'external_id': external_id,
                    'idempotency': 'duplicate',
                    'first_processed_at': first_processed_at.isoformat() if first_processed_at else None
                }
            )
            
            # Increment duplicate counter
            global webhook_duplicates_total
            webhook_duplicates_total += 1
            
            db.commit()
            return {
                "status": "duplicate_ignored",
                "provider": provider,
                "first_processed_at": first_processed_at.isoformat() if first_processed_at else None
            }, 200
        
        # First-time delivery - process the webhook
        logger.info(
            "Processing webhook for first time",
            extra={
                'trace_id': trace_id,
                'tenant_id': tenant_id,
                'provider': provider,
                'external_id': external_id,
                'idempotency': 'first'
            }
        )
        
        # Execute the actual webhook processing
        result = process_fn()
        
        # Mark as processed
        update_query = text("""
            UPDATE idempotency_keys 
            SET first_processed_at = NOW()
            WHERE tenant_id = :tenant_id 
            AND provider = :provider 
            AND external_id = :external_id
        """)
        
        db.execute(update_query, {
            'tenant_id': tenant_id,
            'provider': provider,
            'external_id': external_id
        })
        
        # Increment processed counter
        global webhook_processed_total
        webhook_processed_total += 1
        
        logger.info(
            "Webhook processed successfully",
            extra={
                'trace_id': trace_id,
                'tenant_id': tenant_id,
                'provider': provider,
                'external_id': external_id,
                'idempotency': 'processed'
            }
        )
        
        db.commit()
        return {
            "status": "processed",
            "provider": provider,
            "result": result
        }, 200
        
    except Exception as e:
        # Rollback and remove idempotency key so retry can succeed
        db.rollback()
        
        # Remove the idempotency key
        delete_query = text("""
            DELETE FROM idempotency_keys 
            WHERE tenant_id = :tenant_id 
            AND provider = :provider 
            AND external_id = :external_id
        """)
        
        db.execute(delete_query, {
            'tenant_id': tenant_id,
            'provider': provider,
            'external_id': external_id
        })
        db.commit()
        
        # Increment failure counter
        global webhook_failures_total
        webhook_failures_total += 1
        
        logger.error(
            "Webhook processing failed, key removed for retry",
            extra={
                'trace_id': trace_id,
                'tenant_id': tenant_id,
                'provider': provider,
                'external_id': external_id,
                'idempotency': 'failed',
                'error': str(e)
            },
            exc_info=True
        )
        
        raise
    
    finally:
        db.close()


def cleanup_old_idempotency_keys():
    """
    Cleanup task to remove old idempotency keys.
    Should be run periodically (e.g., via Celery).
    """
    ttl_days = int(os.getenv('IDEMPOTENCY_TTL_DAYS', '90'))
    cutoff_date = datetime.utcnow() - timedelta(days=ttl_days)
    
    db = next(get_db())
    
    try:
        delete_query = text("""
            DELETE FROM idempotency_keys 
            WHERE last_seen_at < :cutoff_date
        """)
        
        result = db.execute(delete_query, {'cutoff_date': cutoff_date})
        deleted_count = result.rowcount
        
        db.commit()
        
        logger.info(
            f"Cleaned up {deleted_count} old idempotency keys older than {ttl_days} days",
            extra={
                'deleted_count': deleted_count,
                'ttl_days': ttl_days,
                'task': 'cleanup_old_idempotency_keys'
            }
        )
        
        # Increment purge metrics
        global webhook_idempotency_purged_total
        webhook_idempotency_purged_total += deleted_count
        
        return deleted_count
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to cleanup old idempotency keys: {e}")
        raise
    
    finally:
        db.close()


def get_idempotency_stats() -> Dict[str, int]:
    """Get current idempotency statistics."""
    return {
        'webhook_processed_total': webhook_processed_total,
        'webhook_duplicates_total': webhook_duplicates_total,
        'webhook_failures_total': webhook_failures_total,
        'webhook_idempotency_purged_total': webhook_idempotency_purged_total
    }
