#931980e753b188c6856ffaed726ef00a
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .database import init_db, SessionLocal
from .routes import webhooks, company, user, backend, sales_rep, sales_manager, calls, bland, call_rail, scheduled_tasks, delete, mobile
from .routes.mobile_routes import mobile_router
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
from app.obs.metrics import metrics

# Setup observability
setup_logging()
setup_tracing()
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
app.include_router(webhooks.router)
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return metrics.get_metrics_response()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)