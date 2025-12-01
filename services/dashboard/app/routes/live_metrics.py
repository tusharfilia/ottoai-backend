"""
Live Metrics API endpoints for real-time KPI tracking
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any
from app.database import get_db
from app.middleware.rbac import require_role
from app.services.live_metrics_service import live_metrics_service
from app.schemas.responses import APIResponse
from app.obs.logging import get_logger
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/live-metrics", tags=["live-metrics", "real-time"])
logger = get_logger(__name__)

@router.get("/current")
@require_role("manager", "csr")
async def get_current_metrics(
    request,
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get current live metrics for the authenticated user's tenant.
    
    Returns real-time KPIs including:
    - Revenue metrics (today, this week, this month)
    - Call metrics (active calls, success rate, duration)
    - Lead metrics (active leads, conversion rate)
    - CSR performance metrics
    """
    try:
        # Get tenant_id from request (set by auth middleware)
        tenant_id = getattr(request.state, 'tenant_id', None)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID not found in request")
        
        # Get current metrics for this tenant
        metrics_data = await live_metrics_service.get_tenant_metrics(tenant_id)
        
        return APIResponse(
            success=True,
            data=metrics_data,
            message="Live metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting live metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve live metrics")

@router.get("/revenue")
@require_role("manager")
async def get_revenue_metrics(
    request,
    period: str = Query("today", description="Time period: today, week, month"),
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get detailed revenue metrics for the specified period.
    
    Args:
        period: Time period to analyze (today, week, month)
    """
    try:
        tenant_id = getattr(request.state, 'tenant_id', None)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID not found in request")
        
        # Get revenue metrics
        metrics_data = await live_metrics_service.get_tenant_metrics(tenant_id)
        revenue_data = metrics_data.get("revenue", {})
        
        # Filter by period if requested
        if period == "today":
            filtered_data = {"today": revenue_data.get("today", 0)}
        elif period == "week":
            filtered_data = {"this_week": revenue_data.get("this_week", 0)}
        elif period == "month":
            filtered_data = {"this_month": revenue_data.get("this_month", 0)}
        else:
            filtered_data = revenue_data
        
        return APIResponse(
            success=True,
            data=filtered_data,
            message=f"Revenue metrics for {period} retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting revenue metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve revenue metrics")

@router.get("/calls")
@require_role("manager", "csr")
async def get_call_metrics(
    request,
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get live call metrics including active calls and performance.
    """
    try:
        tenant_id = getattr(request.state, 'tenant_id', None)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID not found in request")
        
        # Get call metrics
        metrics_data = await live_metrics_service.get_tenant_metrics(tenant_id)
        call_data = metrics_data.get("calls", {})
        
        return APIResponse(
            success=True,
            data=call_data,
            message="Call metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting call metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve call metrics")

@router.get("/leads")
@require_role("manager", "csr")
async def get_lead_metrics(
    request,
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get live lead metrics including conversion rates.
    """
    try:
        tenant_id = getattr(request.state, 'tenant_id', None)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID not found in request")
        
        # Get lead metrics
        metrics_data = await live_metrics_service.get_tenant_metrics(tenant_id)
        lead_data = metrics_data.get("leads", {})
        
        return APIResponse(
            success=True,
            data=lead_data,
            message="Lead metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting lead metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve lead metrics")

@router.get("/csr-performance")
@require_role("manager")
async def get_csr_performance_metrics(
    request,
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get CSR performance metrics including top performers.
    """
    try:
        tenant_id = getattr(request.state, 'tenant_id', None)
        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID not found in request")
        
        # Get CSR metrics
        metrics_data = await live_metrics_service.get_tenant_metrics(tenant_id)
        csr_data = metrics_data.get("csr_performance", {})
        
        return APIResponse(
            success=True,
            data=csr_data,
            message="CSR performance metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting CSR performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve CSR performance metrics")

@router.get("/status")
async def get_metrics_service_status() -> APIResponse:
    """
    Get the status of the live metrics service.
    """
    try:
        status = {
            "running": live_metrics_service.running,
            "update_interval": live_metrics_service.update_interval,
            "last_update": getattr(live_metrics_service, 'last_update', None)
        }
        
        return APIResponse(
            success=True,
            data=status,
            message="Live metrics service status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting metrics service status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve service status")










