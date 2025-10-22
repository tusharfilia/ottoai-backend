"""
Prometheus metrics endpoint for Grafana integration.

Exposes application metrics in Prometheus format.
"""
from fastapi import APIRouter, Response
from app.obs.metrics import metrics

router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    summary="Prometheus metrics",
    description="""
    Exposes application metrics in Prometheus format for Grafana scraping.
    
    **Metrics Exposed**:
    - Request count by endpoint and status code
    - Request latency (P50, P95, P99)
    - Active requests gauge
    - Database connection pool stats
    - Redis connection stats
    - UWC API call stats (when enabled)
    - Business metrics (calls/day, analyses/day)
    
    **No Authentication Required**: Metrics endpoint is public (no PII)
    
    **Grafana Configuration**:
    1. Add Prometheus data source
    2. Set URL to: https://your-backend.fly.dev/metrics
    3. Create dashboards using these metrics
    
    **Example Metrics**:
    ```
    # HELP http_requests_total Total HTTP requests
    # TYPE http_requests_total counter
    http_requests_total{method="GET",endpoint="/health",status="200"} 1523
    
    # HELP http_request_duration_seconds HTTP request latency
    # TYPE http_request_duration_seconds histogram
    http_request_duration_seconds_bucket{le="0.1"} 1420
    http_request_duration_seconds_bucket{le="0.5"} 1510
    http_request_duration_seconds_bucket{le="1.0"} 1520
    ```
    """,
    responses={
        200: {
            "description": "Metrics in Prometheus format",
            "content": {
                "text/plain": {
                    "example": """# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/health",status="200"} 1523

# HELP http_request_duration_seconds HTTP request latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_count 1523
http_request_duration_seconds_sum 342.5"""
                }
            }
        }
    },
    response_class=Response
)
async def get_metrics():
    """
    Return Prometheus-formatted metrics.
    
    This endpoint is scraped by Prometheus/Grafana every 15-60 seconds.
    """
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    
    # Generate metrics in Prometheus format
    metrics_output = generate_latest(metrics.registry)
    
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST
    )




