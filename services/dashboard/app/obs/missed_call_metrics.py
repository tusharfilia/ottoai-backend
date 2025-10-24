"""
Missed Call Queue Metrics Collection
Implements comprehensive metrics for missed call recovery system
"""
import time
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, Info
from app.obs.logging import get_logger

logger = get_logger(__name__)

# Prometheus metrics for missed call queue system
missed_call_queue_length = Gauge(
    'missed_call_queue_length',
    'Current length of missed call queue',
    ['tenant_id', 'status']
)

missed_call_processing_duration_seconds = Histogram(
    'missed_call_processing_duration_seconds',
    'Time taken to process missed call queue entries',
    ['tenant_id', 'status'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

sms_retry_count_total = Counter(
    'sms_retry_count_total',
    'Total number of SMS retry attempts',
    ['tenant_id', 'retry_attempt', 'status']
)

sms_delivery_success_ratio = Gauge(
    'sms_delivery_success_ratio',
    'Ratio of successful SMS deliveries',
    ['tenant_id']
)

missed_call_recovery_rate = Gauge(
    'missed_call_recovery_rate',
    'Rate of successful missed call recoveries',
    ['tenant_id']
)

human_takeover_count = Counter(
    'human_takeover_count_total',
    'Total number of human takeovers',
    ['tenant_id', 'takeover_type']
)

compliance_violations_total = Counter(
    'compliance_violations_total',
    'Total number of compliance violations',
    ['tenant_id', 'violation_type']
)

circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Current state of circuit breaker (0=closed, 1=open, 2=half_open)',
    ['tenant_id', 'service_name']
)

queue_processing_errors_total = Counter(
    'queue_processing_errors_total',
    'Total number of queue processing errors',
    ['tenant_id', 'error_type']
)

class MissedCallMetrics:
    """Metrics collection for missed call queue system"""
    
    def __init__(self):
        self.start_times = {}  # Track processing start times
    
    def record_queue_length(self, tenant_id: str, status: str, count: int):
        """Record current queue length"""
        try:
            missed_call_queue_length.labels(
                tenant_id=tenant_id,
                status=status
            ).set(count)
        except Exception as e:
            logger.error(f"Error recording queue length: {str(e)}")
    
    def start_processing_timer(self, tenant_id: str, queue_id: int):
        """Start processing timer for a queue entry"""
        try:
            timer_key = f"{tenant_id}:{queue_id}"
            self.start_times[timer_key] = time.time()
        except Exception as e:
            logger.error(f"Error starting processing timer: {str(e)}")
    
    def record_processing_duration(self, tenant_id: str, queue_id: int, status: str):
        """Record processing duration for a queue entry"""
        try:
            timer_key = f"{tenant_id}:{queue_id}"
            if timer_key in self.start_times:
                duration = time.time() - self.start_times[timer_key]
                missed_call_processing_duration_seconds.labels(
                    tenant_id=tenant_id,
                    status=status
                ).observe(duration)
                
                # Clean up timer
                del self.start_times[timer_key]
        except Exception as e:
            logger.error(f"Error recording processing duration: {str(e)}")
    
    def record_sms_retry(self, tenant_id: str, retry_attempt: int, status: str):
        """Record SMS retry attempt"""
        try:
            sms_retry_count_total.labels(
                tenant_id=tenant_id,
                retry_attempt=str(retry_attempt),
                status=status
            ).inc()
        except Exception as e:
            logger.error(f"Error recording SMS retry: {str(e)}")
    
    def record_sms_delivery_success(self, tenant_id: str, success: bool):
        """Record SMS delivery success/failure"""
        try:
            # This would typically be calculated from a counter
            # For now, we'll use a simple gauge
            value = 1.0 if success else 0.0
            sms_delivery_success_ratio.labels(tenant_id=tenant_id).set(value)
        except Exception as e:
            logger.error(f"Error recording SMS delivery success: {str(e)}")
    
    def record_recovery_rate(self, tenant_id: str, recovered_count: int, total_count: int):
        """Record missed call recovery rate"""
        try:
            if total_count > 0:
                rate = recovered_count / total_count
                missed_call_recovery_rate.labels(tenant_id=tenant_id).set(rate)
        except Exception as e:
            logger.error(f"Error recording recovery rate: {str(e)}")
    
    def record_human_takeover(self, tenant_id: str, takeover_type: str):
        """Record human takeover event"""
        try:
            human_takeover_count.labels(
                tenant_id=tenant_id,
                takeover_type=takeover_type
            ).inc()
        except Exception as e:
            logger.error(f"Error recording human takeover: {str(e)}")
    
    def record_compliance_violation(self, tenant_id: str, violation_type: str):
        """Record compliance violation"""
        try:
            compliance_violations_total.labels(
                tenant_id=tenant_id,
                violation_type=violation_type
            ).inc()
        except Exception as e:
            logger.error(f"Error recording compliance violation: {str(e)}")
    
    def record_circuit_breaker_state(self, tenant_id: str, service_name: str, state: str):
        """Record circuit breaker state"""
        try:
            state_value = {
                "closed": 0,
                "open": 1,
                "half_open": 2
            }.get(state, 0)
            
            circuit_breaker_state.labels(
                tenant_id=tenant_id,
                service_name=service_name
            ).set(state_value)
        except Exception as e:
            logger.error(f"Error recording circuit breaker state: {str(e)}")
    
    def record_queue_processing_error(self, tenant_id: str, error_type: str):
        """Record queue processing error"""
        try:
            queue_processing_errors_total.labels(
                tenant_id=tenant_id,
                error_type=error_type
            ).inc()
        except Exception as e:
            logger.error(f"Error recording queue processing error: {str(e)}")
    
    def get_metrics_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get metrics summary for a tenant"""
        try:
            # This would typically query Prometheus metrics
            # For now, return a placeholder structure
            return {
                "tenant_id": tenant_id,
                "queue_length": 0,  # Would be queried from Prometheus
                "processing_duration_avg": 0.0,
                "sms_success_rate": 0.0,
                "recovery_rate": 0.0,
                "human_takeovers": 0,
                "compliance_violations": 0,
                "circuit_breaker_states": {},
                "processing_errors": 0
            }
        except Exception as e:
            logger.error(f"Error getting metrics summary: {str(e)}")
            return {}

# Global metrics instance
missed_call_metrics = MissedCallMetrics()
