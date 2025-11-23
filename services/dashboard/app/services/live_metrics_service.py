"""
Live Metrics Service for Real-Time KPI Tracking
Provides real-time metrics for revenue, calls, leads, and CSR performance
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from app.database import SessionLocal
from app.realtime.bus import emit
from app.obs.logging import get_logger
from app.obs.metrics import metrics

logger = get_logger(__name__)

class LiveMetricsService:
    """Service for calculating and broadcasting live metrics."""
    
    def __init__(self):
        self.running = False
        self.update_interval = 30  # Update every 30 seconds
        self.metrics_task = None
    
    async def start(self):
        """Start the live metrics service."""
        if self.running:
            logger.warning("Live metrics service is already running")
            return
        
        self.running = True
        logger.info("Starting live metrics service")
        
        # Start the metrics update loop
        self.metrics_task = asyncio.create_task(self._metrics_update_loop())
    
    async def stop(self):
        """Stop the live metrics service."""
        self.running = False
        if self.metrics_task:
            self.metrics_task.cancel()
        logger.info("Live metrics service stopped")
    
    async def _metrics_update_loop(self):
        """Main loop for updating and broadcasting metrics."""
        while self.running:
            try:
                # Calculate all live metrics
                metrics_data = await self._calculate_live_metrics()
                
                # Broadcast to all tenants
                await self._broadcast_metrics(metrics_data)
                
                # Update metrics (if available)
                if hasattr(metrics, 'set_live_metrics_updated'):
                    metrics.set_live_metrics_updated(time.time())
                
            except Exception as e:
                logger.error(f"Error in metrics update loop: {e}")
            
            # Wait before next update
            await asyncio.sleep(self.update_interval)
    
    async def _calculate_live_metrics(self) -> Dict[str, Any]:
        """Calculate all live metrics."""
        db = SessionLocal()
        try:
            # Get all active tenants
            tenants = await self._get_active_tenants(db)
            
            all_metrics = {}
            
            for tenant in tenants:
                tenant_id = tenant["id"]
                tenant_metrics = await self._calculate_tenant_metrics(db, tenant_id)
                all_metrics[tenant_id] = tenant_metrics
            
            return all_metrics
            
        finally:
            db.close()
    
    async def _get_active_tenants(self, db: Session) -> List[Dict[str, Any]]:
        """Get list of active tenants."""
        try:
            result = db.execute(text("""
                SELECT DISTINCT id, name 
                FROM companies 
                WHERE id IS NOT NULL
            """))
            return [{"id": row[0], "name": row[1]} for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Error getting active tenants: {e}")
            return []
    
    async def _calculate_tenant_metrics(self, db: Session, tenant_id: str) -> Dict[str, Any]:
        """Calculate metrics for a specific tenant."""
        try:
            now = datetime.utcnow()
            today = now.date()
            week_start = today - timedelta(days=today.weekday())
            month_start = today.replace(day=1)
            
            # Revenue metrics
            revenue_metrics = await self._calculate_revenue_metrics(db, tenant_id, today, week_start, month_start)
            
            # Call metrics
            call_metrics = await self._calculate_call_metrics(db, tenant_id, today)
            
            # Lead metrics
            lead_metrics = await self._calculate_lead_metrics(db, tenant_id, today)
            
            # CSR performance metrics
            csr_metrics = await self._calculate_csr_metrics(db, tenant_id, today)
            
            return {
                "timestamp": now.isoformat(),
                "revenue": revenue_metrics,
                "calls": call_metrics,
                "leads": lead_metrics,
                "csr_performance": csr_metrics
            }
            
        except Exception as e:
            logger.error(f"Error calculating metrics for tenant {tenant_id}: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def _calculate_revenue_metrics(self, db: Session, tenant_id: str, today, week_start, month_start) -> Dict[str, Any]:
        """Calculate revenue metrics."""
        try:
            # Today's revenue (from calls where bought = True)
            today_revenue = db.execute(text("""
                SELECT COALESCE(SUM(price_if_bought), 0) as revenue
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) = :today
                AND bought = true
                AND price_if_bought IS NOT NULL
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            # This week's revenue
            week_revenue = db.execute(text("""
                SELECT COALESCE(SUM(price_if_bought), 0) as revenue
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) >= :week_start
                AND bought = true
                AND price_if_bought IS NOT NULL
            """), {"tenant_id": tenant_id, "week_start": week_start}).scalar() or 0
            
            # This month's revenue
            month_revenue = db.execute(text("""
                SELECT COALESCE(SUM(price_if_bought), 0) as revenue
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) >= :month_start
                AND bought = true
                AND price_if_bought IS NOT NULL
            """), {"tenant_id": tenant_id, "month_start": month_start}).scalar() or 0
            
            # Average deal size
            avg_deal_size = db.execute(text("""
                SELECT COALESCE(AVG(price_if_bought), 0) as avg_deal
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) >= :week_start
                AND bought = true
                AND price_if_bought IS NOT NULL
                AND price_if_bought > 0
            """), {"tenant_id": tenant_id, "week_start": week_start}).scalar() or 0
            
            return {
                "today": float(today_revenue),
                "this_week": float(week_revenue),
                "this_month": float(month_revenue),
                "avg_deal_size": float(avg_deal_size)
            }
            
        except Exception as e:
            logger.error(f"Error calculating revenue metrics: {e}")
            return {"error": str(e)}
    
    async def _calculate_call_metrics(self, db: Session, tenant_id: str, today) -> Dict[str, Any]:
        """Calculate call metrics."""
        try:
            # Active calls (calls in progress)
            active_calls = db.execute(text("""
                SELECT COUNT(*) as count
                FROM calls 
                WHERE company_id = :tenant_id 
                AND status IN ('in_progress', 'ringing')
            """), {"tenant_id": tenant_id}).scalar() or 0
            
            # Calls today
            calls_today = db.execute(text("""
                SELECT COUNT(*) as count
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) = :today
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            # Successful calls today
            successful_calls = db.execute(text("""
                SELECT COUNT(*) as count
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) = :today
                AND status = 'completed'
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            # Success rate
            success_rate = (successful_calls / calls_today * 100) if calls_today > 0 else 0
            
            # Average call duration
            avg_duration = db.execute(text("""
                SELECT COALESCE(AVG(last_call_duration), 0) as avg_duration
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) = :today
                AND status = 'completed'
                AND last_call_duration IS NOT NULL
                AND last_call_duration > 0
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            return {
                "active_calls": int(active_calls),
                "calls_today": int(calls_today),
                "successful_calls": int(successful_calls),
                "success_rate": round(success_rate, 1),
                "avg_duration_minutes": round(float(avg_duration) / 60, 1)
            }
            
        except Exception as e:
            logger.error(f"Error calculating call metrics: {e}")
            return {"error": str(e)}
    
    async def _calculate_lead_metrics(self, db: Session, tenant_id: str, today) -> Dict[str, Any]:
        """Calculate lead metrics."""
        try:
            # Active leads (calls created today, treating all as potential leads)
            active_leads = db.execute(text("""
                SELECT COUNT(*) as count
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) = :today
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            # New leads today (unique phone numbers)
            new_leads = db.execute(text("""
                SELECT COUNT(DISTINCT phone_number) as count
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) = :today
                AND phone_number IS NOT NULL
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            # Lead conversion rate (calls that resulted in bookings)
            converted_leads = db.execute(text("""
                SELECT COUNT(*) as count
                FROM calls 
                WHERE company_id = :tenant_id 
                AND DATE(created_at) = :today
                AND booked = true
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            conversion_rate = (converted_leads / new_leads * 100) if new_leads > 0 else 0
            
            return {
                "active_leads": int(active_leads),
                "new_leads_today": int(new_leads),
                "converted_leads": int(converted_leads),
                "conversion_rate": round(conversion_rate, 1)
            }
            
        except Exception as e:
            logger.error(f"Error calculating lead metrics: {e}")
            return {"error": str(e)}
    
    async def _calculate_csr_metrics(self, db: Session, tenant_id: str, today) -> Dict[str, Any]:
        """Calculate CSR performance metrics."""
        try:
            # Get top performing CSR
            top_csr = db.execute(text("""
                SELECT 
                    u.name,
                    COUNT(c.call_id) as calls_handled,
                    ROUND(AVG(CASE WHEN c.status = 'completed' THEN 1 ELSE 0 END) * 100, 1) as success_rate
                FROM sales_reps sr
                LEFT JOIN users u ON sr.user_id = u.id
                LEFT JOIN calls c ON sr.user_id = c.assigned_rep_id 
                AND DATE(c.created_at) = :today
                WHERE sr.company_id = :tenant_id
                GROUP BY sr.user_id, u.name
                ORDER BY calls_handled DESC, success_rate DESC
                LIMIT 1
            """), {"tenant_id": tenant_id, "today": today}).fetchone()
            
            # Overall CSR performance
            total_csr_calls = db.execute(text("""
                SELECT COUNT(*) as count
                FROM calls c
                JOIN sales_reps sr ON c.assigned_rep_id = sr.user_id
                WHERE sr.company_id = :tenant_id
                AND DATE(c.created_at) = :today
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            total_successful_calls = db.execute(text("""
                SELECT COUNT(*) as count
                FROM calls c
                JOIN sales_reps sr ON c.assigned_rep_id = sr.user_id
                WHERE sr.company_id = :tenant_id
                AND DATE(c.created_at) = :today
                AND c.status = 'completed'
            """), {"tenant_id": tenant_id, "today": today}).scalar() or 0
            
            overall_success_rate = (total_successful_calls / total_csr_calls * 100) if total_csr_calls > 0 else 0
            
            return {
                "top_performer": {
                    "name": top_csr[0] if top_csr else "N/A",
                    "calls_handled": int(top_csr[1]) if top_csr else 0,
                    "success_rate": float(top_csr[2]) if top_csr else 0
                },
                "overall": {
                    "total_calls": int(total_csr_calls),
                    "successful_calls": int(total_successful_calls),
                    "success_rate": round(overall_success_rate, 1)
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating CSR metrics: {e}")
            return {"error": str(e)}
    
    async def _broadcast_metrics(self, metrics_data: Dict[str, Any]):
        """Broadcast metrics to all tenants via WebSocket."""
        try:
            for tenant_id, tenant_metrics in metrics_data.items():
                # Emit metrics event for this tenant
                success = emit(
                    event_name="metrics.live_updated",
                    payload=tenant_metrics,
                    tenant_id=tenant_id,
                    severity="info"
                )
                
                if success:
                    logger.debug(f"Live metrics broadcasted to tenant {tenant_id}")
                else:
                    logger.warning(f"Failed to broadcast metrics to tenant {tenant_id}")
            
            logger.info(f"Live metrics broadcasted to {len(metrics_data)} tenants")
            
        except Exception as e:
            logger.error(f"Error broadcasting metrics: {e}")
    
    async def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get current metrics for a specific tenant."""
        db = SessionLocal()
        try:
            return await self._calculate_tenant_metrics(db, tenant_id)
        finally:
            db.close()


# Global live metrics service instance
live_metrics_service = LiveMetricsService()
