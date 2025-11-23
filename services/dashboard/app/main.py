#931980e753b188c6856ffaed726ef00a
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .database import init_db, SessionLocal
from .routes import company, user, backend, sales_rep, sales_manager, calls, bland, call_rail, scheduled_tasks, delete, mobile, health, websocket, rag, analysis, followups, clones, gdpr, metrics, sms_handler, enhanced_callrail, missed_call_queue, live_metrics, post_call_analysis, contact_cards, leads, appointments, rep_shifts, recording_sessions
from .routes import webhooks as webhooks_module
from .routes.mobile_routes import mobile_router
from .routes.webhook_handlers.uwc import router as uwc_webhooks
from .routes.shunya_webhook import router as shunya_webhook
from .routes.ai_internal import router as ai_internal_router
from .services.bland_ai import BlandAI
from .services.missing_reports_service import check_missing_reports
from datetime import datetime, timedelta
import asyncio
from .models import scheduled_call, call
from sqlalchemy import and_

# Import centralized configuration
from app.config import settings

# Import observability components
from app.obs.logging import setup_logging, get_logger
from app.obs.tracing import setup_tracing, instrument_fastapi, instrument_requests, instrument_sqlalchemy
from app.obs.middleware import ObservabilityMiddleware
from app.obs.errors import register_error_handlers
from app.obs.metrics import metrics as metrics_collector
from app.obs.sentry import setup_sentry

# Setup observability
setup_logging()
setup_tracing()
setup_sentry()  # Initialize Sentry for error tracking
instrument_requests()
instrument_sqlalchemy()

logger = get_logger(__name__)

app = FastAPI(title="TrueView API")

# Instrument FastAPI with OpenTelemetry
instrument_fastapi(app)

# Initialize BlandAI service but don't start schedulers yet
bland_ai_service = BlandAI(auto_start_schedulers=False)

# Import middleware
from app.middleware.tenant import TenantContextMiddleware
from app.middleware.rate_limiter import RateLimitMiddleware

# Register error handlers
register_error_handlers(app)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Observability middleware (must be early in the stack)
app.add_middleware(ObservabilityMiddleware)

# Tenant context middleware
app.add_middleware(TenantContextMiddleware)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

#931980e753b188c6856ffaed726ef00a
# Include routers
app.include_router(health.router)  # Health checks first
app.include_router(websocket.router)  # WebSocket endpoint
app.include_router(webhooks_module.router)
app.include_router(uwc_webhooks)  # UWC webhook handlers
app.include_router(shunya_webhook)  # Shunya job webhook handlers
app.include_router(rag.router)  # RAG/Ask Otto endpoints
app.include_router(analysis.router)  # Call analysis endpoints
app.include_router(followups.router)  # Follow-up drafts endpoints
app.include_router(clones.router)  # Personal clone training endpoints
app.include_router(gdpr.router)  # GDPR compliance endpoints
app.include_router(metrics.router)  # Prometheus metrics for Grafana
app.include_router(company.router)
app.include_router(user.router)
app.include_router(backend.router)
app.include_router(sales_rep.router)
app.include_router(sales_manager.router)
app.include_router(calls.router)
app.include_router(bland.router)
app.include_router(call_rail.router)
app.include_router(scheduled_tasks.router)
app.include_router(delete.router)
app.include_router(sms_handler.router)  # SMS handling endpoints
app.include_router(enhanced_callrail.router)  # Enhanced CallRail webhook handlers
app.include_router(missed_call_queue.router)  # Missed call queue management
app.include_router(live_metrics.router)  # Live metrics and real-time KPIs
app.include_router(post_call_analysis.router)  # Post-call analysis and coaching
app.include_router(contact_cards.router)  # Contact card domain endpoints
app.include_router(leads.router)  # Lead domain endpoints
app.include_router(appointments.router)  # Appointment domain endpoints
from app.routes.lead_pool import router as lead_pool_router
app.include_router(lead_pool_router)  # Lead pool management endpoints
app.include_router(rep_shifts.router)  # Rep shift management endpoints
app.include_router(recording_sessions.router)  # Recording session endpoints
app.include_router(ai_internal_router)  # Internal AI API endpoints for Shunya/UWC

# Include admin routes
try:
    from app.routes.admin import openai_stats
    app.include_router(openai_stats.router)
except ImportError:
    logger.warning("Admin routes not available - skipping")

# Include mobile routes
app.include_router(mobile_router)
app.include_router(mobile.router)

# Task to periodically check for missing reports and send notifications
async def check_missing_reports_task():
    """
    Background task to periodically check for appointments that should have reports
    and send notifications to sales reps.
    """
    while True:
        try:
            logger.info("Running missing reports check...")
            
            # Create a new database session
            db = SessionLocal()
            try:
                # Check for missing reports
                notifications_sent = check_missing_reports(db)
                logger.info(f"Missing reports check completed. Sent {notifications_sent} notifications.")
            finally:
                # Close the database session
                db.close()
                
            # Wait for 6 hours before checking again
            await asyncio.sleep(6 * 60 * 60)  # 6 hours in seconds
        except Exception as e:
            logger.error(f"Error in missing reports checker: {str(e)}")
            # Still wait before trying again to avoid runaway errors
            await asyncio.sleep(30 * 60)  # 30 minutes in seconds

# Initialize database tables and scheduler on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    # Start the schedulers after the application has started
    # bland_ai_service.start_scheduler()
    # bland_ai_service.start_scheduled_calls_checker()
    
    # Start the missing reports checker in the background
    asyncio.create_task(check_missing_reports_task())
    logger.info("Started missing reports checker task")
    
    # Start the missed call queue processor
    from app.services.queue_processor import queue_processor
    await queue_processor.start()
    logger.info("Started missed call queue processor")
    
    # Start the live metrics service
    from app.services.live_metrics_service import live_metrics_service
    await live_metrics_service.start()
    logger.info("Started live metrics service")
    
    # Start the post-call analysis service
    from app.services.post_call_analysis_service import post_call_analysis_service
    await post_call_analysis_service.start()
    logger.info("Started post-call analysis service")

@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return metrics_collector.get_metrics_response()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    # Stop the live metrics service
    from app.services.live_metrics_service import live_metrics_service
    await live_metrics_service.stop()
    logger.info("Stopped live metrics service")
    
    # Stop the post-call analysis service
    from app.services.post_call_analysis_service import post_call_analysis_service
    await post_call_analysis_service.stop()
    logger.info("Stopped post-call analysis service")
    
    # Stop the missed call queue processor
    from app.services.queue_processor import queue_processor
    await queue_processor.stop()
    logger.info("Stopped missed call queue processor")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)