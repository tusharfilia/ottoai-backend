"""
Post-Call Analysis API endpoints
Provides analysis of completed calls, coaching recommendations, and performance insights
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any, List
from app.database import get_db
from app.middleware.rbac import require_role
from app.services.post_call_analysis_service import post_call_analysis_service
from app.schemas.responses import APIResponse
from app.obs.logging import get_logger
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/post-call-analysis", tags=["post-call-analysis", "coaching"])
logger = get_logger(__name__)

@router.get("/call/{call_id}")
@require_role("manager", "csr")
async def get_call_analysis(
    call_id: int,
    request,
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get post-call analysis for a specific call.
    
    Returns:
    - Call metrics (duration, success, etc.)
    - AI insights and recommendations
    - Performance score
    - Coaching recommendations
    """
    try:
        # Get analysis results
        analysis_result = await post_call_analysis_service.get_call_analysis(call_id)
        
        if not analysis_result:
            raise HTTPException(status_code=404, detail="Analysis not found for this call")
        
        return APIResponse(
            success=True,
            data=analysis_result,
            message="Call analysis retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting call analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve call analysis")

@router.get("/sales-rep/{sales_rep_id}/performance")
@require_role("manager")
async def get_sales_rep_performance(
    sales_rep_id: str,
    days: int = Query(30, description="Number of days to analyze", ge=1, le=365),
    request=None,
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get performance analysis for a specific sales rep.
    
    Args:
        sales_rep_id: ID of the sales rep
        days: Number of days to analyze (1-365)
    
    Returns:
    - Performance metrics over time
    - Coaching recommendations summary
    - Score trends
    - Areas for improvement
    """
    try:
        # Get performance analysis
        performance_data = await post_call_analysis_service.get_sales_rep_performance(sales_rep_id, days)
        
        return APIResponse(
            success=True,
            data=performance_data,
            message=f"Performance analysis for sales rep {sales_rep_id} retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting sales rep performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance analysis")

@router.get("/coaching-recommendations")
@require_role("manager", "csr")
async def get_coaching_recommendations(
    sales_rep_id: Optional[str] = Query(None, description="Filter by sales rep ID"),
    category: Optional[str] = Query(None, description="Filter by recommendation category"),
    priority: Optional[str] = Query(None, description="Filter by priority (high, medium, low)"),
    days: int = Query(7, description="Number of days to look back", ge=1, le=30),
    request=None,
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get coaching recommendations based on recent call analysis.
    
    Args:
        sales_rep_id: Optional filter by specific sales rep
        category: Optional filter by recommendation category
        priority: Optional filter by priority level
        days: Number of days to look back (1-30)
    
    Returns:
    - List of coaching recommendations
    - Categorized by type and priority
    - Actionable insights for improvement
    """
    try:
        # Build query filters
        filters = []
        params = {"days": days}
        
        if sales_rep_id:
            filters.append("ca.sales_rep_id = :sales_rep_id")
            params["sales_rep_id"] = sales_rep_id
        
        if category:
            filters.append("JSON_EXTRACT(ca.coaching_recommendations, '$[*].category') LIKE :category")
            params["category"] = f"%{category}%"
        
        if priority:
            filters.append("JSON_EXTRACT(ca.coaching_recommendations, '$[*].priority') LIKE :priority")
            params["priority"] = f"%{priority}%"
        
        # Build the query
        where_clause = " AND ".join(filters) if filters else "1=1"
        
        # Get recommendations from recent analyses
        results = db.execute(f"""
            SELECT 
                ca.call_id,
                ca.sales_rep_id,
                ca.coaching_recommendations,
                ca.analyzed_at,
                c.duration,
                c.status,
                sr.name as sales_rep_name
            FROM call_analysis ca
            JOIN calls c ON ca.call_id = c.call_id
            LEFT JOIN sales_reps sr ON ca.sales_rep_id = sr.sales_rep_id
            WHERE ca.analyzed_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
            AND {where_clause}
            ORDER BY ca.analyzed_at DESC
        """, params).fetchall()
        
        # Process recommendations
        all_recommendations = []
        for result in results:
            if result.coaching_recommendations:
                for rec in result.coaching_recommendations:
                    rec_data = dict(rec)
                    rec_data.update({
                        "call_id": result.call_id,
                        "sales_rep_id": result.sales_rep_id,
                        "sales_rep_name": result.sales_rep_name,
                        "analyzed_at": result.analyzed_at.isoformat() if result.analyzed_at else None,
                        "call_duration": result.duration,
                        "call_status": result.status
                    })
                    all_recommendations.append(rec_data)
        
        # Sort by priority and date
        priority_order = {"high": 3, "medium": 2, "low": 1}
        all_recommendations.sort(
            key=lambda x: (priority_order.get(x.get('priority', 'low'), 1), x.get('analyzed_at', '')),
            reverse=True
        )
        
        return APIResponse(
            success=True,
            data={
                "recommendations": all_recommendations,
                "total_count": len(all_recommendations),
                "filters_applied": {
                    "sales_rep_id": sales_rep_id,
                    "category": category,
                    "priority": priority,
                    "days": days
                }
            },
            message="Coaching recommendations retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting coaching recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve coaching recommendations")

@router.get("/performance-summary")
@require_role("manager")
async def get_performance_summary(
    days: int = Query(7, description="Number of days to analyze", ge=1, le=30),
    request=None,
    db: Session = Depends(get_db)
) -> APIResponse:
    """
    Get overall performance summary for the company.
    
    Args:
        days: Number of days to analyze (1-30)
    
    Returns:
    - Company-wide performance metrics
    - Top performers
    - Areas needing attention
    - Coaching opportunities
    """
    try:
        # Get company-wide performance data
        results = db.execute("""
            SELECT 
                ca.sales_rep_id,
                sr.name as sales_rep_name,
                COUNT(*) as total_calls,
                AVG(JSON_EXTRACT(ca.performance_score, '$.overall_score')) as avg_score,
                AVG(c.duration) as avg_duration,
                SUM(CASE WHEN c.status = 'completed' THEN 1 ELSE 0 END) as successful_calls
            FROM call_analysis ca
            JOIN calls c ON ca.call_id = c.call_id
            LEFT JOIN sales_reps sr ON ca.sales_rep_id = sr.sales_rep_id
            WHERE ca.analyzed_at >= DATE_SUB(NOW(), INTERVAL :days DAY)
            GROUP BY ca.sales_rep_id, sr.name
            ORDER BY avg_score DESC
        """, {"days": days}).fetchall()
        
        if not results:
            return APIResponse(
                success=True,
                data={"message": "No performance data available for the specified period"},
                message="Performance summary retrieved successfully"
            )
        
        # Process results
        sales_reps = []
        total_calls = 0
        total_successful = 0
        all_scores = []
        
        for result in results:
            rep_data = {
                "sales_rep_id": result.sales_rep_id,
                "sales_rep_name": result.sales_rep_name,
                "total_calls": result.total_calls,
                "avg_score": round(result.avg_score or 0, 2),
                "avg_duration_minutes": round((result.avg_duration or 0) / 60, 2),
                "success_rate": round((result.successful_calls / result.total_calls) * 100, 2) if result.total_calls > 0 else 0
            }
            sales_reps.append(rep_data)
            
            total_calls += result.total_calls
            total_successful += result.successful_calls
            all_scores.append(result.avg_score or 0)
        
        # Calculate company-wide metrics
        company_avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        company_success_rate = (total_successful / total_calls * 100) if total_calls > 0 else 0
        
        # Identify top performers and areas for improvement
        top_performers = [rep for rep in sales_reps if rep['avg_score'] >= 80][:3]
        needs_improvement = [rep for rep in sales_reps if rep['avg_score'] < 60]
        
        return APIResponse(
            success=True,
            data={
                "period_days": days,
                "company_metrics": {
                    "total_calls_analyzed": total_calls,
                    "average_score": round(company_avg_score, 2),
                    "success_rate": round(company_success_rate, 2)
                },
                "sales_reps": sales_reps,
                "top_performers": top_performers,
                "needs_improvement": needs_improvement,
                "insights": {
                    "total_sales_reps": len(sales_reps),
                    "high_performers": len([rep for rep in sales_reps if rep['avg_score'] >= 80]),
                    "coaching_opportunities": len(needs_improvement)
                }
            },
            message="Performance summary retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance summary")

@router.get("/status")
async def get_analysis_service_status() -> APIResponse:
    """
    Get the status of the post-call analysis service.
    """
    try:
        status = {
            "running": post_call_analysis_service.running,
            "analysis_interval": post_call_analysis_service.analysis_interval,
            "openai_available": post_call_analysis_service.openai_client is not None
        }
        
        return APIResponse(
            success=True,
            data=status,
            message="Post-call analysis service status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting analysis service status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve service status")








