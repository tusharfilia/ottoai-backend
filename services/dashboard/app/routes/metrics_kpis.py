"""
KPI Metrics API endpoints for role-scoped metrics.

Provides endpoints for:
- CSR overview metrics
- Sales Rep metrics (per-rep + team)
- Executive metrics (CSR tab + Sales tab)
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List

from app.database import get_db
from app.middleware.rbac import require_role
from app.core.tenant import get_tenant_id
from app.services.metrics_service import MetricsService
from app.schemas.responses import APIResponse
from app.schemas.metrics import (
    CSRMetrics,
    SalesRepMetrics,
    SalesTeamMetrics,
    ExecCSRMetrics,
    ExecSalesMetrics,
    CSRBookingTrend,
    CSRUnbookedAppointmentsResponse,
    CSRTopObjectionsResponse,
    CSRObjectionCallsResponse,
    AutoQueuedLeadsResponse,
    CSRMissedCallRecoveryResponse,
    ExecCompanyOverviewMetrics,
    ExecCSRDashboardMetrics,
    ExecMissedCallRecoveryMetrics,
    ExecSalesTeamDashboardMetrics,
    CSROverviewSelfResponse,
    CSRBookingTrendSelfResponse,
    UnbookedCallsSelfResponse,
    CSRObjectionsSelfResponse,
    CallsByObjectionSelfResponse,
    CSRMissedCallsSelfResponse,
    MissedLeadsSelfResponse,
    RideAlongAppointmentsResponse,
    SalesOpportunitiesResponse,
    SalesRepTodayAppointment,
    SalesRepFollowupTask,
    SalesRepMeetingDetail
)
from app.obs.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/metrics", tags=["metrics", "kpis"])


def parse_date_param(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO8601 date string to datetime.
    
    Handles both date-only (YYYY-MM-DD) and full ISO8601 formats.
    
    Args:
        date_str: ISO8601 date string or None
    
    Returns:
        datetime object or None
    """
    if not date_str:
        return None
    
    try:
        # Try full ISO8601 format first
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            # Try date-only format (YYYY-MM-DD)
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {date_str}. Expected ISO8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)"
            )


@router.get("/csr/overview", response_model=APIResponse[CSRMetrics])
@require_role("csr", "manager")
async def get_csr_overview_metrics(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional, defaults to 30 days ago)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional, defaults to now)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get CSR overview metrics.
    
    **Roles**: csr, manager
    - CSR can see tenant-wide overview (per-user filtering to be added later)
    - Manager can see tenant-wide overview
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: CSRMetrics with calls, qualification, booking, compliance, and followup metrics.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to) or datetime.utcnow()
        start = parse_date_param(date_from) or (end - timedelta(days=30))
        
        # Get CSR user ID from request state
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        # For CSR role, scope to their own data; for manager, return tenant-wide
        csr_user_id = user_id if user_role == "csr" else None
        
        service = MetricsService(db)
        metrics = await service.get_csr_overview_metrics(
            csr_user_id=csr_user_id,
            tenant_id=tenant_id,
            start=start,
            end=end
        )
        
        return APIResponse(success=True, data=metrics)
    
    except Exception as e:
        logger.error(f"Error computing CSR overview metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute CSR metrics: {str(e)}")


@router.get("/sales/rep/{rep_id}", response_model=APIResponse[SalesRepMetrics])
@require_role("manager")
async def get_sales_rep_metrics(
    request: Request,
    rep_id: str,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get sales rep overview metrics for a specific rep.
    
    **Roles**: manager (sales_rep can call for themselves - to be added later)
    
    **Query Parameters**:
    - `rep_id`: Sales rep user ID (path parameter)
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: SalesRepMetrics with appointments, outcomes, compliance, sentiment, and followup metrics.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        service = MetricsService(db)
        metrics = await service.get_sales_rep_overview_metrics(
            tenant_id=tenant_id,
            rep_id=rep_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=metrics)
    
    except Exception as e:
        logger.error(f"Error computing sales rep metrics for {rep_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute sales rep metrics: {str(e)}")


@router.get("/sales/team", response_model=APIResponse[SalesTeamMetrics])
@require_role("manager")
async def get_sales_team_metrics(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get aggregate sales team metrics for all reps in the company.
    
    **Roles**: manager
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: SalesTeamMetrics with team aggregates and per-rep summaries.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        service = MetricsService(db)
        metrics = await service.get_sales_team_metrics(
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=metrics)
    
    except Exception as e:
        logger.error(f"Error computing sales team metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute sales team metrics: {str(e)}")


@router.get("/exec/csr", response_model=APIResponse[ExecCSRMetrics])
@require_role("manager")
async def get_exec_csr_metrics(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get executive-level CSR metrics (company-wide).
    
    **Roles**: manager
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: ExecCSRMetrics with company-wide CSR metrics.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        service = MetricsService(db)
        metrics = await service.get_exec_csr_metrics(
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=metrics)
    
    except Exception as e:
        logger.error(f"Error computing exec CSR metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute exec CSR metrics: {str(e)}")


@router.get("/exec/sales", response_model=APIResponse[ExecSalesMetrics])
@require_role("manager")
async def get_exec_sales_metrics(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get executive-level Sales metrics (company-wide).
    
    **Roles**: manager
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: ExecSalesMetrics with company-wide sales metrics.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        service = MetricsService(db)
        metrics = await service.get_exec_sales_metrics(
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=metrics)
    
    except Exception as e:
        logger.error(f"Error computing exec sales metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute exec sales metrics: {str(e)}")


@router.get("/csr/booking-trend", response_model=APIResponse[CSRBookingTrend])
@require_role("csr", "manager")
async def get_csr_booking_trend(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    granularity: str = Query("month", description="Time granularity: day, week, month"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get CSR booking trend over time (time series).
    
    **Roles**: csr, manager
    - CSR sees their own booking trend
    - Manager can see any CSR's trend (csr_id param to be added later)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    - `granularity`: Time bucket size (day, week, month)
    
    **Returns**: CSRBookingTrend with time series points.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        if user_role != "csr":
            raise HTTPException(status_code=403, detail="Only CSR role can access this endpoint")
        
        csr_user_id = user_id
        
        if granularity not in ["day", "week", "month"]:
            raise HTTPException(status_code=400, detail="granularity must be one of: day, week, month")
        
        service = MetricsService(db)
        trend = await service.get_csr_booking_trend(
            tenant_id=tenant_id,
            csr_user_id=csr_user_id,
            date_from=start,
            date_to=end,
            granularity=granularity
        )
        
        return APIResponse(success=True, data=trend)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing CSR booking trend: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute booking trend: {str(e)}")


@router.get("/csr/unbooked-appointments", response_model=APIResponse[CSRUnbookedAppointmentsResponse])
@require_role("csr", "manager")
async def get_csr_unbooked_appointments(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get list of unbooked appointments/calls for a CSR.
    
    **Roles**: csr, manager
    - CSR sees their own unbooked appointments
    - Manager can see any CSR's unbooked appointments (csr_id param to be added later)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: CSRUnbookedAppointmentsResponse with unbooked items.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        if user_role != "csr":
            raise HTTPException(status_code=403, detail="Only CSR role can access this endpoint")
        
        csr_user_id = user_id
        
        service = MetricsService(db)
        response = await service.get_csr_unbooked_appointments(
            tenant_id=tenant_id,
            csr_user_id=csr_user_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSR unbooked appointments: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get unbooked appointments: {str(e)}")


@router.get("/csr/objections/top", response_model=APIResponse[CSRTopObjectionsResponse])
@require_role("csr", "manager")
async def get_csr_top_objections(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    limit: int = Query(5, description="Number of top objections to return"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get top objections for a CSR.
    
    **Roles**: csr, manager
    - CSR sees their own top objections
    - Manager can see any CSR's objections (csr_id param to be added later)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    - `limit`: Number of top objections to return (default: 5)
    
    **Returns**: CSRTopObjectionsResponse with top objections.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        if user_role != "csr":
            raise HTTPException(status_code=403, detail="Only CSR role can access this endpoint")
        
        csr_user_id = user_id
        
        service = MetricsService(db)
        response = await service.get_csr_top_objections(
            tenant_id=tenant_id,
            csr_user_id=csr_user_id,
            date_from=start,
            date_to=end,
            limit=limit
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSR top objections: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get top objections: {str(e)}")


@router.get("/csr/objections/{objection_key}/calls", response_model=APIResponse[CSRObjectionCallsResponse])
@require_role("csr", "manager")
async def get_csr_objection_calls(
    request: Request,
    objection_key: str,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get calls where a specific objection occurred.
    
    **Roles**: csr, manager
    - CSR sees their own calls with this objection
    - Manager can see any CSR's calls (csr_id param to be added later)
    
    **Path Parameters**:
    - `objection_key`: The objection key to filter by
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: CSRObjectionCallsResponse with matching calls.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        if user_role != "csr":
            raise HTTPException(status_code=403, detail="Only CSR role can access this endpoint")
        
        csr_user_id = user_id
        
        service = MetricsService(db)
        response = await service.get_csr_objection_calls(
            tenant_id=tenant_id,
            csr_user_id=csr_user_id,
            objection_key=objection_key,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSR objection calls: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get objection calls: {str(e)}")


@router.get("/csr/auto-queued-leads", response_model=APIResponse[AutoQueuedLeadsResponse])
@require_role("csr", "manager")
async def get_auto_queued_leads(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get auto-queued leads (AI recovery from missed calls).
    
    **Roles**: csr, manager
    - Shared across all CSRs in the company (not CSR-specific)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: AutoQueuedLeadsResponse with auto-queued leads.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        service = MetricsService(db)
        response = await service.get_auto_queued_leads(
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except Exception as e:
        logger.error(f"Error getting auto-queued leads: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get auto-queued leads: {str(e)}")


@router.get("/csr/missed-call-recovery", response_model=APIResponse[CSRMissedCallRecoveryResponse])
@require_role("csr", "manager")
async def get_csr_missed_call_recovery(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get missed call recovery overview for a CSR.
    
    **Roles**: csr, manager
    - CSR sees their own missed call recovery metrics
    - Manager can see any CSR's recovery metrics (csr_id param to be added later)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: CSRMissedCallRecoveryResponse with metrics and lead lists.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        if user_role != "csr":
            raise HTTPException(status_code=403, detail="Only CSR role can access this endpoint")
        
        csr_user_id = user_id
        
        service = MetricsService(db)
        response = await service.get_csr_missed_call_recovery(
            tenant_id=tenant_id,
            csr_user_id=csr_user_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSR missed call recovery: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get missed call recovery: {str(e)}")


# Executive Dashboard endpoints

@router.get("/exec/company-overview", response_model=APIResponse[ExecCompanyOverviewMetrics])
@require_role("manager")
async def get_exec_company_overview(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional, defaults to 30 days ago)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional, defaults to now)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get executive company-wide overview metrics.
    
    **Roles**: manager (exec context)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: ExecCompanyOverviewMetrics with company-wide funnel, attribution, and "who is dropping the ball".
    """
    try:
        # Parse dates
        end = parse_date_param(date_to) or datetime.utcnow()
        start = parse_date_param(date_from) or (end - timedelta(days=30))
        
        service = MetricsService(db)
        response = await service.get_exec_company_overview_metrics(
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exec company overview: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get company overview: {str(e)}")


@router.get("/exec/csr/dashboard", response_model=APIResponse[ExecCSRDashboardMetrics])
@require_role("manager")
async def get_exec_csr_dashboard(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional, defaults to 30 days ago)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional, defaults to now)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get executive CSR dashboard metrics (company-wide CSR view).
    
    **Roles**: manager (exec context)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: ExecCSRDashboardMetrics with overview, trends, objections, and coaching opportunities.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to) or datetime.utcnow()
        start = parse_date_param(date_from) or (end - timedelta(days=30))
        
        service = MetricsService(db)
        response = await service.get_exec_csr_dashboard_metrics(
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exec CSR dashboard: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get CSR dashboard: {str(e)}")


@router.get("/exec/missed-calls", response_model=APIResponse[ExecMissedCallRecoveryMetrics])
@require_role("manager")
async def get_exec_missed_call_recovery(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional, defaults to 30 days ago)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional, defaults to now)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get executive missed call recovery metrics (company-wide).
    
    **Roles**: manager (exec context)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: ExecMissedCallRecoveryMetrics with company-wide missed call recovery stats.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to) or datetime.utcnow()
        start = parse_date_param(date_from) or (end - timedelta(days=30))
        
        service = MetricsService(db)
        response = await service.get_exec_missed_call_recovery_metrics(
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exec missed call recovery: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get missed call recovery: {str(e)}")


@router.get("/exec/sales/dashboard", response_model=APIResponse[ExecSalesTeamDashboardMetrics])
@require_role("manager")
async def get_exec_sales_team_dashboard(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional, defaults to 30 days ago)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional, defaults to now)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get executive sales team dashboard metrics.
    
    **Roles**: manager (exec context)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: ExecSalesTeamDashboardMetrics with overview, team stats, reps, and objections.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to) or datetime.utcnow()
        start = parse_date_param(date_from) or (end - timedelta(days=30))
        
        service = MetricsService(db)
        response = await service.get_exec_sales_team_dashboard_metrics(
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exec sales team dashboard: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sales team dashboard: {str(e)}")


# CSR Self-Scoped Endpoints

@router.get("/csr/overview/self", response_model=APIResponse[CSROverviewSelfResponse])
@require_role("csr")
async def get_csr_overview_self(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional, defaults to 30 days ago)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional, defaults to now)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get CSR overview metrics for self.
    
    **Roles**: csr only
    - Auto-resolves CSR from auth (no csr_id param needed)
    - Filtered to that CSR only (uses Call.owner_id)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: CSROverviewSelfResponse with all CSR metrics plus top_missed_booking_reason.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to) or datetime.utcnow()
        start = parse_date_param(date_from) or (end - timedelta(days=30))
        
        # Get CSR user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        response = await service.get_csr_overview_self(
            csr_user_id=user_id,
            tenant_id=tenant_id,
            start=start,
            end=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSR overview self: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get CSR overview: {str(e)}")


@router.get("/csr/booking-trend/self", response_model=APIResponse[CSRBookingTrendSelfResponse])
@require_role("csr")
async def get_csr_booking_trend_self(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    granularity: str = Query("month", description="Time bucket size: day, week, or month"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get CSR booking trend for self with summary.
    
    **Roles**: csr only
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    - `granularity`: Time bucket size (day, week, month) - default: month
    
    **Returns**: CSRBookingTrendSelfResponse with summary and trend points.
    All booking/qualification derived ONLY from Shunya fields.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Validate granularity
        if granularity not in ["day", "week", "month"]:
            raise HTTPException(status_code=400, detail="granularity must be 'day', 'week', or 'month'")
        
        # Get CSR user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        response = await service.get_csr_booking_trend_self(
            csr_user_id=user_id,
            tenant_id=tenant_id,
            date_from=start,
            date_to=end,
            granularity=granularity
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSR booking trend self: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get booking trend: {str(e)}")


@router.get("/calls/unbooked/self", response_model=APIResponse[UnbookedCallsSelfResponse])
@require_role("csr")
async def get_calls_unbooked_self(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get paginated unbooked calls for CSR self.
    
    **Roles**: csr only
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    - `page`: Page number (1-indexed)
    - `page_size`: Page size (1-200)
    
    **Returns**: UnbookedCallsSelfResponse with paginated unbooked calls.
    Unbooked = anything where Shunya says NOT booking_status == "booked".
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        response = await service.get_csr_unbooked_calls_self(
            csr_user_id=user_id,
            tenant_id=tenant_id,
            date_from=start,
            date_to=end,
            page=page,
            page_size=page_size
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting unbooked calls self: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get unbooked calls: {str(e)}")


@router.get("/csr/objections/self", response_model=APIResponse[CSRObjectionsSelfResponse])
@require_role("csr")
async def get_csr_objections_self(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get CSR objections for self view.
    
    **Roles**: csr only
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: CSRObjectionsSelfResponse with top and all objections.
    Uses Shunya CallAnalysis.objections + booking/qualification fields.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        response = await service.get_csr_objections_self(
            csr_user_id=user_id,
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSR objections self: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get objections: {str(e)}")


@router.get("/calls/by-objection/self", response_model=APIResponse[CallsByObjectionSelfResponse])
@require_role("csr")
async def get_calls_by_objection_self(
    request: Request,
    objection: str = Query(..., description="Objection key to filter by"),
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get paginated calls filtered by objection for CSR self.
    
    **Roles**: csr only
    
    **Query Parameters**:
    - `objection`: Objection key to filter by (required)
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    - `page`: Page number (1-indexed)
    - `page_size`: Page size (1-200)
    
    **Returns**: CallsByObjectionSelfResponse with paginated calls.
    Filters calls where Shunya objections list contains that objection string.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        response = await service.get_csr_calls_by_objection_self(
            csr_user_id=user_id,
            tenant_id=tenant_id,
            objection=objection,
            date_from=start,
            date_to=end,
            page=page,
            page_size=page_size
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting calls by objection self: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get calls by objection: {str(e)}")


@router.get("/csr/missed-calls/self", response_model=APIResponse[CSRMissedCallsSelfResponse])
@require_role("csr")
async def get_csr_missed_calls_self(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get CSR missed calls metrics for self.
    
    **Roles**: csr only
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: CSRMissedCallsSelfResponse with missed call metrics.
    Wrapper using existing missed-call logic but scoped to that CSR.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Get CSR user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        response = await service.get_csr_missed_calls_self(
            csr_user_id=user_id,
            tenant_id=tenant_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CSR missed calls self: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get missed calls: {str(e)}")


@router.get("/leads/missed/self", response_model=APIResponse[MissedLeadsSelfResponse])
@require_role("csr")
async def get_leads_missed_self(
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status: booked, pending, or dead"),
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get paginated missed leads for CSR self.
    
    **Roles**: csr only
    
    **Query Parameters**:
    - `status`: Filter by status (booked, pending, dead) - optional
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    - `page`: Page number (1-indexed)
    - `page_size`: Page size (1-200)
    
    **Returns**: MissedLeadsSelfResponse with paginated missed leads.
    Uses Shunya booking/outcome for status, plus Otto's call/twilio interaction counts for attempt_count.
    """
    try:
        # Parse dates
        end = parse_date_param(date_to)
        start = parse_date_param(date_from)
        
        # Validate status
        if status and status not in ["booked", "pending", "dead"]:
            raise HTTPException(status_code=400, detail="status must be 'booked', 'pending', or 'dead'")
        
        # Get CSR user ID from auth
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        response = await service.get_csr_missed_leads_self(
            csr_user_id=user_id,
            tenant_id=tenant_id,
            status=status,
            date_from=start,
            date_to=end,
            page=page,
            page_size=page_size
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting missed leads self: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get missed leads: {str(e)}")


# Exec Endpoints

@router.get("/exec/ride-along", response_model=APIResponse[RideAlongAppointmentsResponse])
@require_role("manager")
async def get_ride_along_appointments(
    request: Request,
    date: Optional[str] = Query(None, description="Date to filter by (ISO8601, optional, defaults to today)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Page size"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get paginated ride-along appointments for exec view.
    
    **Roles**: manager only
    
    **Query Parameters**:
    - `date`: Date to filter by (ISO8601, optional, defaults to today)
    - `page`: Page number (1-indexed)
    - `page_size`: Page size (1-200)
    
    **Returns**: RideAlongAppointmentsResponse with paginated appointments.
    Status/outcome must be derived from Shunya RecordingAnalysis.outcome + Otto local appointment state.
    """
    try:
        # Parse date
        if date:
            date_obj = parse_date_param(date)
            if date_obj:
                date_obj = date_obj.date()
            else:
                date_obj = datetime.utcnow().date()
        else:
            date_obj = datetime.utcnow().date()
        
        service = MetricsService(db)
        response = await service.get_ride_along_appointments(
            tenant_id=tenant_id,
            date=datetime.combine(date_obj, datetime.min.time()),
            page=page,
            page_size=page_size
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ride-along appointments: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get ride-along appointments: {str(e)}")


@router.get("/sales/opportunities", response_model=APIResponse[SalesOpportunitiesResponse])
@require_role("manager")
async def get_sales_opportunities(
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get sales opportunities per rep.
    
    **Roles**: manager only
    
    **Returns**: SalesOpportunitiesResponse with opportunities per rep.
    Uses Task + Shunya booking/outcome to identify pending leads per rep.
    """
    try:
        service = MetricsService(db)
        response = await service.get_sales_opportunities(
            tenant_id=tenant_id
        )
        
        return APIResponse(success=True, data=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sales opportunities: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sales opportunities: {str(e)}")


# Sales Rep App Endpoints

@router.get("/sales/rep/overview/self", response_model=APIResponse[SalesRepMetrics])
@require_role("sales_rep")
async def get_sales_rep_overview_self(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional, defaults to 30 days ago)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional, defaults to now)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get sales rep overview metrics (self-scoped).
    
    **Roles**: sales_rep (can only see their own metrics)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional, defaults to 30 days ago)
    - `date_to`: End date (ISO8601, optional, defaults to now)
    
    **Returns**: SalesRepMetrics with appointments, outcomes, compliance, sentiment, and followup metrics.
    Uses Shunya's RecordingAnalysis.outcome for won/lost decisions.
    """
    try:
        # Get rep user ID from request state
        rep_id = getattr(request.state, 'user_id', None)
        if not rep_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        # Parse dates
        end = parse_date_param(date_to) or datetime.utcnow()
        start = parse_date_param(date_from) or (end - timedelta(days=30))
        
        service = MetricsService(db)
        metrics = await service.get_sales_rep_overview_metrics(
            tenant_id=tenant_id,
            rep_id=rep_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=metrics)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing sales rep overview metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compute sales rep metrics: {str(e)}")


@router.get("/appointments/today/self", response_model=APIResponse[List[SalesRepTodayAppointment]])
@require_role("sales_rep")
async def get_sales_rep_today_appointments(
    request: Request,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get today's appointments for the logged-in sales rep.
    
    **Roles**: sales_rep (can only see their own appointments)
    
    **Returns**: List of SalesRepTodayAppointment for today, sorted by scheduled_time.
    """
    try:
        # Get rep user ID from request state
        rep_id = getattr(request.state, 'user_id', None)
        if not rep_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        appointments = await service.get_sales_rep_today_appointments(
            tenant_id=tenant_id,
            rep_id=rep_id,
            today=None  # Defaults to current date
        )
        
        return APIResponse(success=True, data=appointments)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting today's appointments: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get today's appointments: {str(e)}")


@router.get("/tasks/sales-rep/self", response_model=APIResponse[List[SalesRepFollowupTask]])
@require_role("sales_rep")
async def get_sales_rep_followups_self(
    request: Request,
    date_from: Optional[str] = Query(None, description="Start date (ISO8601, optional)"),
    date_to: Optional[str] = Query(None, description="End date (ISO8601, optional)"),
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get follow-up tasks for the logged-in sales rep.
    
    **Roles**: sales_rep (can only see their own tasks)
    
    **Query Parameters**:
    - `date_from`: Start date (ISO8601, optional)
    - `date_to`: End date (ISO8601, optional)
    
    **Returns**: List of SalesRepFollowupTask assigned to the rep.
    """
    try:
        # Get rep user ID from request state
        rep_id = getattr(request.state, 'user_id', None)
        if not rep_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        # Parse dates
        start = parse_date_param(date_from)
        end = parse_date_param(date_to)
        
        service = MetricsService(db)
        tasks = await service.get_sales_rep_followups(
            tenant_id=tenant_id,
            rep_id=rep_id,
            date_from=start,
            date_to=end
        )
        
        return APIResponse(success=True, data=tasks)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sales rep followups: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sales rep followups: {str(e)}")


@router.get("/meetings/{appointment_id}/analysis", response_model=APIResponse[SalesRepMeetingDetail])
@require_role("sales_rep")
async def get_sales_rep_meeting_analysis(
    request: Request,
    appointment_id: str,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db)
):
    """
    Get meeting analysis detail for a sales rep appointment.
    
    **Roles**: sales_rep (can only see their own appointments)
    
    **Path Parameters**:
    - `appointment_id`: Appointment ID
    
    **Returns**: SalesRepMeetingDetail with AI summary, transcript, objections, compliance, sentiment, outcome, and follow-up recommendations.
    """
    try:
        # Get rep user ID from request state
        rep_id = getattr(request.state, 'user_id', None)
        if not rep_id:
            raise HTTPException(status_code=401, detail="User ID not found in request")
        
        service = MetricsService(db)
        detail = await service.get_sales_rep_meeting_detail(
            tenant_id=tenant_id,
            rep_id=rep_id,
            appointment_id=appointment_id
        )
        
        return APIResponse(success=True, data=detail)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting meeting analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get meeting analysis: {str(e)}")

