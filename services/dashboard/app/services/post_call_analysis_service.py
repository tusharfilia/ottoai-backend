"""
Post-Call Analysis Service
Analyzes completed calls and provides insights, coaching recommendations, and performance metrics
Uses Schema 2 (modern UWC-compatible schema) for storage
"""
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
from app.database import SessionLocal
from app.realtime.bus import emit
from app.obs.logging import get_logger
from app.obs.metrics import metrics
import openai
from app.config import settings

logger = get_logger(__name__)

class PostCallAnalysisService:
    """Service for analyzing completed calls and providing insights."""
    
    def __init__(self):
        self.running = False
        self.analysis_interval = 60  # Analyze every 60 seconds
        self.analysis_task = None
        self.openai_client = None
        
        # Initialize OpenAI client
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def start(self):
        """Start the post-call analysis service."""
        if self.running:
            logger.warning("Post-call analysis service is already running")
            return
        
        self.running = True
        logger.info("Starting post-call analysis service")
        
        # Start the analysis loop
        self.analysis_task = asyncio.create_task(self._analysis_loop())
    
    async def stop(self):
        """Stop the post-call analysis service."""
        self.running = False
        if self.analysis_task:
            self.analysis_task.cancel()
        logger.info("Post-call analysis service stopped")
    
    async def _analysis_loop(self):
        """Main loop for analyzing completed calls."""
        while self.running:
            try:
                # Find calls that need analysis
                calls_to_analyze = await self._get_calls_for_analysis()
                
                for call in calls_to_analyze:
                    try:
                        # Analyze the call
                        analysis_result = await self._analyze_call(call)
                        
                        # Store analysis results
                        await self._store_analysis_results(call['call_id'], analysis_result)
                        
                        # Emit analysis event
                        await self._emit_analysis_event(call, analysis_result)
                        
                        logger.info(f"Analyzed call {call['call_id']}")
                        
                    except Exception as e:
                        logger.error(f"Error analyzing call {call['call_id']}: {e}")
                
                # Update metrics
                if hasattr(metrics, 'set_post_call_analysis_updated'):
                    metrics.set_post_call_analysis_updated(time.time())
                
            except Exception as e:
                logger.error(f"Error in post-call analysis loop: {e}")
            
            # Wait before next analysis cycle
            await asyncio.sleep(self.analysis_interval)
    
    async def _get_calls_for_analysis(self) -> List[Dict[str, Any]]:
        """
        Get calls that need analysis.
        Only analyzes calls that don't already have UWC analysis.
        """
        db = SessionLocal()
        try:
            # Find completed calls from the last hour that haven't been analyzed by UWC
            # This service acts as a fallback for calls without UWC analysis
            result = db.execute(text("""
                SELECT 
                    c.call_id,
                    c.company_id as tenant_id,  -- Use tenant_id for Schema 2
                    c.assigned_rep_id as sales_rep_id,
                    c.phone_number as caller_number,
                    c.last_call_duration as duration,
                    c.status,
                    c.created_at,
                    NULL as recording_url,
                    u.name as sales_rep_name,
                    comp.name as company_name
                FROM calls c
                LEFT JOIN sales_reps sr ON c.assigned_rep_id = sr.user_id
                LEFT JOIN users u ON sr.user_id = u.id
                LEFT JOIN companies comp ON c.company_id = comp.id
                WHERE c.status = 'completed'
                AND c.created_at >= :since
                AND c.call_id NOT IN (
                    SELECT DISTINCT call_id 
                    FROM call_analysis 
                    WHERE call_id IS NOT NULL
                    AND uwc_job_id IS NOT NULL  -- Only skip if UWC analysis exists
                )
                ORDER BY c.created_at DESC
                LIMIT 10
            """), {"since": datetime.utcnow() - timedelta(hours=1)})
            
            return [dict(row._mapping) for row in result.fetchall()]
            
        finally:
            db.close()
    
    async def _analyze_call(self, call: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a completed call and provide insights."""
        try:
            # Basic call metrics
            call_metrics = await self._calculate_call_metrics(call)
            
            # AI-powered analysis (if OpenAI is available)
            ai_insights = await self._get_ai_insights(call)
            
            # Coaching recommendations
            coaching_recommendations = await self._generate_coaching_recommendations(call, call_metrics, ai_insights)
            
            # Performance scoring
            performance_score = await self._calculate_performance_score(call, call_metrics, ai_insights)
            
            return {
                "call_id": call['call_id'],
                "tenant_id": call.get('tenant_id') or call.get('company_id'),  # Support both for compatibility
                "sales_rep_id": call['sales_rep_id'],
                "analyzed_at": datetime.utcnow().isoformat(),
                "call_metrics": call_metrics,
                "ai_insights": ai_insights,
                "coaching_recommendations": coaching_recommendations,
                "performance_score": performance_score,
                "analysis_version": "1.0"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing call {call['call_id']}: {e}")
            return {
                "call_id": call['call_id'],
                "error": str(e),
                "analyzed_at": datetime.utcnow().isoformat()
            }
    
    async def _calculate_call_metrics(self, call: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate basic call metrics."""
        try:
            duration = call.get('duration', 0)
            
            # Duration analysis
            duration_minutes = duration / 60 if duration else 0
            duration_category = "short" if duration_minutes < 5 else "medium" if duration_minutes < 15 else "long"
            
            # Success indicators (basic)
            is_successful = call.get('status') == 'completed'
            
            return {
                "duration_seconds": duration,
                "duration_minutes": round(duration_minutes, 2),
                "duration_category": duration_category,
                "is_successful": is_successful,
                "call_type": "inbound" if call.get('caller_number') else "outbound"
            }
            
        except Exception as e:
            logger.error(f"Error calculating call metrics: {e}")
            return {"error": str(e)}
    
    async def _get_ai_insights(self, call: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI-powered insights about the call."""
        if not self.openai_client:
            return {"ai_available": False, "message": "OpenAI not configured"}
        
        try:
            # For now, we'll use basic analysis since we don't have transcripts
            # In the future, this would analyze the actual call transcript
            
            call_metrics = await self._calculate_call_metrics(call)
            
            # Basic AI insights based on call data
            insights = {
                "ai_available": True,
                "call_quality": "good" if call_metrics.get('duration_minutes', 0) > 5 else "needs_improvement",
                "engagement_level": "high" if call_metrics.get('duration_minutes', 0) > 10 else "medium",
                "follow_up_needed": call_metrics.get('is_successful', False),
                "key_insights": [
                    f"Call duration: {call_metrics.get('duration_minutes', 0):.1f} minutes",
                    f"Call type: {call_metrics.get('call_type', 'unknown')}",
                    f"Success status: {'Completed' if call_metrics.get('is_successful') else 'Incomplete'}"
                ]
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting AI insights: {e}")
            return {"ai_available": False, "error": str(e)}
    
    async def _generate_coaching_recommendations(self, call: Dict[str, Any], call_metrics: Dict[str, Any], ai_insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate coaching recommendations based on call analysis."""
        recommendations = []
        
        try:
            duration_minutes = call_metrics.get('duration_minutes', 0)
            is_successful = call_metrics.get('is_successful', False)
            
            # Duration-based recommendations
            if duration_minutes < 2:
                recommendations.append({
                    "category": "call_duration",
                    "priority": "high",
                    "title": "Call Too Short",
                    "description": "Call ended very quickly. Consider asking more qualifying questions.",
                    "suggestion": "Practice open-ended questions to engage customers longer."
                })
            elif duration_minutes > 30:
                recommendations.append({
                    "category": "call_duration",
                    "priority": "medium",
                    "title": "Long Call Duration",
                    "description": "Call was quite long. Consider being more direct.",
                    "suggestion": "Practice getting to the point faster while maintaining rapport."
                })
            
            # Success-based recommendations
            if not is_successful:
                recommendations.append({
                    "category": "call_outcome",
                    "priority": "high",
                    "title": "Call Not Completed",
                    "description": "Call did not complete successfully.",
                    "suggestion": "Review call handling process and customer engagement techniques."
                })
            
            # General recommendations
            if duration_minutes > 5 and is_successful:
                recommendations.append({
                    "category": "positive_feedback",
                    "priority": "low",
                    "title": "Good Call Performance",
                    "description": "Call completed successfully with good duration.",
                    "suggestion": "Keep up the good work! Consider sharing techniques with team."
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating coaching recommendations: {e}")
            return [{"error": str(e)}]
    
    async def _calculate_performance_score(self, call: Dict[str, Any], call_metrics: Dict[str, Any], ai_insights: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall performance score for the call."""
        try:
            score = 0
            max_score = 100
            factors = []
            
            # Duration factor (30 points)
            duration_minutes = call_metrics.get('duration_minutes', 0)
            if duration_minutes >= 5:
                duration_score = min(30, duration_minutes * 3)
                score += duration_score
                factors.append(f"Duration: {duration_score}/30")
            else:
                factors.append(f"Duration: 0/30 (too short)")
            
            # Success factor (40 points)
            if call_metrics.get('is_successful', False):
                score += 40
                factors.append("Success: 40/40")
            else:
                factors.append("Success: 0/40")
            
            # Call quality factor (30 points)
            if ai_insights.get('call_quality') == 'good':
                score += 30
                factors.append("Quality: 30/30")
            else:
                score += 15
                factors.append("Quality: 15/30")
            
            # Performance level
            if score >= 80:
                level = "excellent"
            elif score >= 60:
                level = "good"
            elif score >= 40:
                level = "fair"
            else:
                level = "needs_improvement"
            
            return {
                "overall_score": score,
                "max_score": max_score,
                "performance_level": level,
                "scoring_factors": factors,
                "calculated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance score: {e}")
            return {"error": str(e)}
    
    async def _store_analysis_results(self, call_id: int, analysis_result: Dict[str, Any]):
        """
        Store analysis results in the database using Schema 2 (modern UWC-compatible schema).
        
        This service acts as a fallback for calls that don't have UWC analysis yet.
        Maps legacy analysis data structure to the modern schema.
        """
        db = SessionLocal()
        try:
            tenant_id = analysis_result.get('tenant_id') or analysis_result.get('company_id')
            if not tenant_id:
                logger.error(f"Cannot store analysis for call {call_id}: missing tenant_id/company_id")
                return
            
            # Check if UWC analysis already exists (don't overwrite)
            existing = db.execute(text("""
                SELECT id FROM call_analysis 
                WHERE call_id = :call_id 
                AND uwc_job_id IS NOT NULL 
                AND uwc_job_id NOT LIKE 'legacy_analysis_%'
            """), {"call_id": call_id}).fetchone()
            
            if existing:
                logger.info(f"Skipping storage for call {call_id} - UWC analysis already exists")
                return
            
            # Generate UUID for id and placeholder uwc_job_id
            analysis_id = str(uuid.uuid4())
            legacy_uwc_job_id = f"legacy_analysis_{analysis_id}"
            
            # Map legacy data to Schema 2
            call_metrics = analysis_result.get('call_metrics', {})
            ai_insights = analysis_result.get('ai_insights', {})
            coaching_recommendations = analysis_result.get('coaching_recommendations', [])
            performance_score = analysis_result.get('performance_score', {})
            
            # Extract sentiment/engagement from AI insights if available
            sentiment_score = ai_insights.get('sentiment_score') or ai_insights.get('engagement_level')
            if isinstance(sentiment_score, str):
                # Map string values to float
                sentiment_map = {"positive": 0.8, "neutral": 0.5, "negative": 0.2, "good": 0.8, "medium": 0.5, "poor": 0.2}
                sentiment_score = sentiment_map.get(sentiment_score.lower(), 0.5)
            
            engagement_score = ai_insights.get('engagement_level')
            if isinstance(engagement_score, str):
                engagement_map = {"high": 0.8, "medium": 0.5, "low": 0.2}
                engagement_score = engagement_map.get(engagement_score.lower(), 0.5)
            
            # Map coaching_recommendations to coaching_tips format
            coaching_tips = []
            if isinstance(coaching_recommendations, list):
                for rec in coaching_recommendations:
                    if isinstance(rec, dict):
                        coaching_tips.append({
                            "tip": rec.get('title') or rec.get('description', ''),
                            "priority": rec.get('priority', 'medium'),
                            "category": rec.get('category', 'general'),
                            "description": rec.get('description') or rec.get('suggestion', '')
                        })
            
            # Extract performance metrics
            overall_score = performance_score.get('overall_score', 0) if isinstance(performance_score, dict) else 0
            max_score = performance_score.get('max_score', 100) if isinstance(performance_score, dict) else 100
            conversion_probability = overall_score / max_score if max_score > 0 else 0
            
            # Determine lead quality from performance score
            lead_quality = None
            if overall_score >= 80:
                lead_quality = "hot"
            elif overall_score >= 60:
                lead_quality = "warm"
            elif overall_score >= 40:
                lead_quality = "qualified"
            else:
                lead_quality = "cold"
            
            # Calculate talk time ratio if available (placeholder - would need transcript)
            talk_time_ratio = None
            
            # Insert using Schema 2
            db.execute(text("""
                INSERT INTO call_analysis (
                    id, call_id, tenant_id, uwc_job_id,
                    sentiment_score, engagement_score,
                    coaching_tips,
                    lead_quality, conversion_probability,
                    talk_time_ratio,
                    analyzed_at, analysis_version, created_at
                ) VALUES (
                    :id, :call_id, :tenant_id, :uwc_job_id,
                    :sentiment_score, :engagement_score,
                    CAST(:coaching_tips AS jsonb),
                    :lead_quality, :conversion_probability,
                    :talk_time_ratio,
                    :analyzed_at, :analysis_version, :created_at
                )
            """), {
                "id": analysis_id,
                "call_id": call_id,
                "tenant_id": tenant_id,
                "uwc_job_id": legacy_uwc_job_id,
                "sentiment_score": sentiment_score,
                "engagement_score": engagement_score,
                "coaching_tips": json.dumps(coaching_tips) if coaching_tips else None,
                "lead_quality": lead_quality,
                "conversion_probability": conversion_probability,
                "talk_time_ratio": talk_time_ratio,
                "analyzed_at": datetime.utcnow(),
                "analysis_version": analysis_result.get('analysis_version', 'legacy_v1'),
                "created_at": datetime.utcnow()
            })
            
            db.commit()
            logger.info(f"Stored legacy analysis results for call {call_id} (ID: {analysis_id})")
            
        except Exception as e:
            logger.error(f"Error storing analysis results: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _emit_analysis_event(self, call: Dict[str, Any], analysis_result: Dict[str, Any]):
        """Emit analysis event for real-time updates."""
        try:
            success = emit(
                event_name="call.analysis.completed",
                payload={
                    "call_id": call['call_id'],
                    "company_id": call['company_id'],
                    "sales_rep_id": call['sales_rep_id'],
                    "analysis_result": analysis_result
                },
                tenant_id=call['company_id'],
                user_id=call['sales_rep_id'],
                severity="info"
            )
            
            if success:
                logger.debug(f"Analysis event emitted for call {call['call_id']}")
            else:
                logger.warning(f"Failed to emit analysis event for call {call['call_id']}")
                
        except Exception as e:
            logger.error(f"Error emitting analysis event: {e}")
    
    async def get_call_analysis(self, call_id: int) -> Optional[Dict[str, Any]]:
        """Get analysis results for a specific call."""
        db = SessionLocal()
        try:
            result = db.execute(text("""
                SELECT * FROM call_analysis 
                WHERE call_id = :call_id
                ORDER BY analyzed_at DESC
                LIMIT 1
            """), {"call_id": call_id}).fetchone()
            
            if result:
                return dict(result._mapping)
            return None
            
        finally:
            db.close()
    
    async def get_sales_rep_performance(self, sales_rep_id: str, days: int = 30) -> Dict[str, Any]:
        """Get performance analysis for a sales rep over the specified period."""
        db = SessionLocal()
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Get analysis results for the sales rep
            results = db.execute(text("""
                SELECT 
                    ca.performance_score,
                    ca.call_metrics,
                    ca.coaching_recommendations,
                    ca.analyzed_at,
                    c.duration,
                    c.status
                FROM call_analysis ca
                JOIN calls c ON ca.call_id = c.call_id
                WHERE ca.sales_rep_id = :sales_rep_id
                AND ca.analyzed_at >= :since_date
                ORDER BY ca.analyzed_at DESC
            """), {"sales_rep_id": sales_rep_id, "since_date": since_date}).fetchall()
            
            if not results:
                return {"message": "No analysis data available"}
            
            # Calculate aggregate metrics
            scores = [r.performance_score.get('overall_score', 0) for r in results if r.performance_score]
            avg_score = sum(scores) / len(scores) if scores else 0
            
            # Count recommendations by category
            all_recommendations = []
            for result in results:
                if result.coaching_recommendations:
                    all_recommendations.extend(result.coaching_recommendations)
            
            recommendation_counts = {}
            for rec in all_recommendations:
                category = rec.get('category', 'unknown')
                recommendation_counts[category] = recommendation_counts.get(category, 0) + 1
            
            return {
                "sales_rep_id": sales_rep_id,
                "period_days": days,
                "total_calls_analyzed": len(results),
                "average_score": round(avg_score, 2),
                "recommendation_breakdown": recommendation_counts,
                "recent_analyses": [dict(r._mapping) for r in results[:5]]  # Last 5 analyses
            }
            
        finally:
            db.close()


# Global post-call analysis service instance
post_call_analysis_service = PostCallAnalysisService()



















from app.database import SessionLocal
from app.realtime.bus import emit
from app.obs.logging import get_logger
from app.obs.metrics import metrics
import openai
from app.config import settings

logger = get_logger(__name__)

class PostCallAnalysisService:
    """Service for analyzing completed calls and providing insights."""
    
    def __init__(self):
        self.running = False
        self.analysis_interval = 60  # Analyze every 60 seconds
        self.analysis_task = None
        self.openai_client = None
        
        # Initialize OpenAI client
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def start(self):
        """Start the post-call analysis service."""
        if self.running:
            logger.warning("Post-call analysis service is already running")
            return
        
        self.running = True
        logger.info("Starting post-call analysis service")
        
        # Start the analysis loop
        self.analysis_task = asyncio.create_task(self._analysis_loop())
    
    async def stop(self):
        """Stop the post-call analysis service."""
        self.running = False
        if self.analysis_task:
            self.analysis_task.cancel()
        logger.info("Post-call analysis service stopped")
    
    async def _analysis_loop(self):
        """Main loop for analyzing completed calls."""
        while self.running:
            try:
                # Find calls that need analysis
                calls_to_analyze = await self._get_calls_for_analysis()
                
                for call in calls_to_analyze:
                    try:
                        # Analyze the call
                        analysis_result = await self._analyze_call(call)
                        
                        # Store analysis results
                        await self._store_analysis_results(call['call_id'], analysis_result)
                        
                        # Emit analysis event
                        await self._emit_analysis_event(call, analysis_result)
                        
                        logger.info(f"Analyzed call {call['call_id']}")
                        
                    except Exception as e:
                        logger.error(f"Error analyzing call {call['call_id']}: {e}")
                
                # Update metrics
                if hasattr(metrics, 'set_post_call_analysis_updated'):
                    metrics.set_post_call_analysis_updated(time.time())
                
            except Exception as e:
                logger.error(f"Error in post-call analysis loop: {e}")
            
            # Wait before next analysis cycle
            await asyncio.sleep(self.analysis_interval)
    
    async def _get_calls_for_analysis(self) -> List[Dict[str, Any]]:
        """
        Get calls that need analysis.
        Only analyzes calls that don't already have UWC analysis.
        """
        db = SessionLocal()
        try:
            # Find completed calls from the last hour that haven't been analyzed by UWC
            # This service acts as a fallback for calls without UWC analysis
            result = db.execute(text("""
                SELECT 
                    c.call_id,
                    c.company_id as tenant_id,  -- Use tenant_id for Schema 2
                    c.assigned_rep_id as sales_rep_id,
                    c.phone_number as caller_number,
                    c.last_call_duration as duration,
                    c.status,
                    c.created_at,
                    NULL as recording_url,
                    u.name as sales_rep_name,
                    comp.name as company_name
                FROM calls c
                LEFT JOIN sales_reps sr ON c.assigned_rep_id = sr.user_id
                LEFT JOIN users u ON sr.user_id = u.id
                LEFT JOIN companies comp ON c.company_id = comp.id
                WHERE c.status = 'completed'
                AND c.created_at >= :since
                AND c.call_id NOT IN (
                    SELECT DISTINCT call_id 
                    FROM call_analysis 
                    WHERE call_id IS NOT NULL
                    AND uwc_job_id IS NOT NULL  -- Only skip if UWC analysis exists
                )
                ORDER BY c.created_at DESC
                LIMIT 10
            """), {"since": datetime.utcnow() - timedelta(hours=1)})
            
            return [dict(row._mapping) for row in result.fetchall()]
            
        finally:
            db.close()
    
    async def _analyze_call(self, call: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a completed call and provide insights."""
        try:
            # Basic call metrics
            call_metrics = await self._calculate_call_metrics(call)
            
            # AI-powered analysis (if OpenAI is available)
            ai_insights = await self._get_ai_insights(call)
            
            # Coaching recommendations
            coaching_recommendations = await self._generate_coaching_recommendations(call, call_metrics, ai_insights)
            
            # Performance scoring
            performance_score = await self._calculate_performance_score(call, call_metrics, ai_insights)
            
            return {
                "call_id": call['call_id'],
                "tenant_id": call.get('tenant_id') or call.get('company_id'),  # Support both for compatibility
                "sales_rep_id": call['sales_rep_id'],
                "analyzed_at": datetime.utcnow().isoformat(),
                "call_metrics": call_metrics,
                "ai_insights": ai_insights,
                "coaching_recommendations": coaching_recommendations,
                "performance_score": performance_score,
                "analysis_version": "1.0"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing call {call['call_id']}: {e}")
            return {
                "call_id": call['call_id'],
                "error": str(e),
                "analyzed_at": datetime.utcnow().isoformat()
            }
    
    async def _calculate_call_metrics(self, call: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate basic call metrics."""
        try:
            duration = call.get('duration', 0)
            
            # Duration analysis
            duration_minutes = duration / 60 if duration else 0
            duration_category = "short" if duration_minutes < 5 else "medium" if duration_minutes < 15 else "long"
            
            # Success indicators (basic)
            is_successful = call.get('status') == 'completed'
            
            return {
                "duration_seconds": duration,
                "duration_minutes": round(duration_minutes, 2),
                "duration_category": duration_category,
                "is_successful": is_successful,
                "call_type": "inbound" if call.get('caller_number') else "outbound"
            }
            
        except Exception as e:
            logger.error(f"Error calculating call metrics: {e}")
            return {"error": str(e)}
    
    async def _get_ai_insights(self, call: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI-powered insights about the call."""
        if not self.openai_client:
            return {"ai_available": False, "message": "OpenAI not configured"}
        
        try:
            # For now, we'll use basic analysis since we don't have transcripts
            # In the future, this would analyze the actual call transcript
            
            call_metrics = await self._calculate_call_metrics(call)
            
            # Basic AI insights based on call data
            insights = {
                "ai_available": True,
                "call_quality": "good" if call_metrics.get('duration_minutes', 0) > 5 else "needs_improvement",
                "engagement_level": "high" if call_metrics.get('duration_minutes', 0) > 10 else "medium",
                "follow_up_needed": call_metrics.get('is_successful', False),
                "key_insights": [
                    f"Call duration: {call_metrics.get('duration_minutes', 0):.1f} minutes",
                    f"Call type: {call_metrics.get('call_type', 'unknown')}",
                    f"Success status: {'Completed' if call_metrics.get('is_successful') else 'Incomplete'}"
                ]
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting AI insights: {e}")
            return {"ai_available": False, "error": str(e)}
    
    async def _generate_coaching_recommendations(self, call: Dict[str, Any], call_metrics: Dict[str, Any], ai_insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate coaching recommendations based on call analysis."""
        recommendations = []
        
        try:
            duration_minutes = call_metrics.get('duration_minutes', 0)
            is_successful = call_metrics.get('is_successful', False)
            
            # Duration-based recommendations
            if duration_minutes < 2:
                recommendations.append({
                    "category": "call_duration",
                    "priority": "high",
                    "title": "Call Too Short",
                    "description": "Call ended very quickly. Consider asking more qualifying questions.",
                    "suggestion": "Practice open-ended questions to engage customers longer."
                })
            elif duration_minutes > 30:
                recommendations.append({
                    "category": "call_duration",
                    "priority": "medium",
                    "title": "Long Call Duration",
                    "description": "Call was quite long. Consider being more direct.",
                    "suggestion": "Practice getting to the point faster while maintaining rapport."
                })
            
            # Success-based recommendations
            if not is_successful:
                recommendations.append({
                    "category": "call_outcome",
                    "priority": "high",
                    "title": "Call Not Completed",
                    "description": "Call did not complete successfully.",
                    "suggestion": "Review call handling process and customer engagement techniques."
                })
            
            # General recommendations
            if duration_minutes > 5 and is_successful:
                recommendations.append({
                    "category": "positive_feedback",
                    "priority": "low",
                    "title": "Good Call Performance",
                    "description": "Call completed successfully with good duration.",
                    "suggestion": "Keep up the good work! Consider sharing techniques with team."
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating coaching recommendations: {e}")
            return [{"error": str(e)}]
    
    async def _calculate_performance_score(self, call: Dict[str, Any], call_metrics: Dict[str, Any], ai_insights: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall performance score for the call."""
        try:
            score = 0
            max_score = 100
            factors = []
            
            # Duration factor (30 points)
            duration_minutes = call_metrics.get('duration_minutes', 0)
            if duration_minutes >= 5:
                duration_score = min(30, duration_minutes * 3)
                score += duration_score
                factors.append(f"Duration: {duration_score}/30")
            else:
                factors.append(f"Duration: 0/30 (too short)")
            
            # Success factor (40 points)
            if call_metrics.get('is_successful', False):
                score += 40
                factors.append("Success: 40/40")
            else:
                factors.append("Success: 0/40")
            
            # Call quality factor (30 points)
            if ai_insights.get('call_quality') == 'good':
                score += 30
                factors.append("Quality: 30/30")
            else:
                score += 15
                factors.append("Quality: 15/30")
            
            # Performance level
            if score >= 80:
                level = "excellent"
            elif score >= 60:
                level = "good"
            elif score >= 40:
                level = "fair"
            else:
                level = "needs_improvement"
            
            return {
                "overall_score": score,
                "max_score": max_score,
                "performance_level": level,
                "scoring_factors": factors,
                "calculated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance score: {e}")
            return {"error": str(e)}
    
    async def _store_analysis_results(self, call_id: int, analysis_result: Dict[str, Any]):
        """
        Store analysis results in the database using Schema 2 (modern UWC-compatible schema).
        
        This service acts as a fallback for calls that don't have UWC analysis yet.
        Maps legacy analysis data structure to the modern schema.
        """
        db = SessionLocal()
        try:
            tenant_id = analysis_result.get('tenant_id') or analysis_result.get('company_id')
            if not tenant_id:
                logger.error(f"Cannot store analysis for call {call_id}: missing tenant_id/company_id")
                return
            
            # Check if UWC analysis already exists (don't overwrite)
            existing = db.execute(text("""
                SELECT id FROM call_analysis 
                WHERE call_id = :call_id 
                AND uwc_job_id IS NOT NULL 
                AND uwc_job_id NOT LIKE 'legacy_analysis_%'
            """), {"call_id": call_id}).fetchone()
            
            if existing:
                logger.info(f"Skipping storage for call {call_id} - UWC analysis already exists")
                return
            
            # Generate UUID for id and placeholder uwc_job_id
            analysis_id = str(uuid.uuid4())
            legacy_uwc_job_id = f"legacy_analysis_{analysis_id}"
            
            # Map legacy data to Schema 2
            call_metrics = analysis_result.get('call_metrics', {})
            ai_insights = analysis_result.get('ai_insights', {})
            coaching_recommendations = analysis_result.get('coaching_recommendations', [])
            performance_score = analysis_result.get('performance_score', {})
            
            # Extract sentiment/engagement from AI insights if available
            sentiment_score = ai_insights.get('sentiment_score') or ai_insights.get('engagement_level')
            if isinstance(sentiment_score, str):
                # Map string values to float
                sentiment_map = {"positive": 0.8, "neutral": 0.5, "negative": 0.2, "good": 0.8, "medium": 0.5, "poor": 0.2}
                sentiment_score = sentiment_map.get(sentiment_score.lower(), 0.5)
            
            engagement_score = ai_insights.get('engagement_level')
            if isinstance(engagement_score, str):
                engagement_map = {"high": 0.8, "medium": 0.5, "low": 0.2}
                engagement_score = engagement_map.get(engagement_score.lower(), 0.5)
            
            # Map coaching_recommendations to coaching_tips format
            coaching_tips = []
            if isinstance(coaching_recommendations, list):
                for rec in coaching_recommendations:
                    if isinstance(rec, dict):
                        coaching_tips.append({
                            "tip": rec.get('title') or rec.get('description', ''),
                            "priority": rec.get('priority', 'medium'),
                            "category": rec.get('category', 'general'),
                            "description": rec.get('description') or rec.get('suggestion', '')
                        })
            
            # Extract performance metrics
            overall_score = performance_score.get('overall_score', 0) if isinstance(performance_score, dict) else 0
            max_score = performance_score.get('max_score', 100) if isinstance(performance_score, dict) else 100
            conversion_probability = overall_score / max_score if max_score > 0 else 0
            
            # Determine lead quality from performance score
            lead_quality = None
            if overall_score >= 80:
                lead_quality = "hot"
            elif overall_score >= 60:
                lead_quality = "warm"
            elif overall_score >= 40:
                lead_quality = "qualified"
            else:
                lead_quality = "cold"
            
            # Calculate talk time ratio if available (placeholder - would need transcript)
            talk_time_ratio = None
            
            # Insert using Schema 2
            db.execute(text("""
                INSERT INTO call_analysis (
                    id, call_id, tenant_id, uwc_job_id,
                    sentiment_score, engagement_score,
                    coaching_tips,
                    lead_quality, conversion_probability,
                    talk_time_ratio,
                    analyzed_at, analysis_version, created_at
                ) VALUES (
                    :id, :call_id, :tenant_id, :uwc_job_id,
                    :sentiment_score, :engagement_score,
                    CAST(:coaching_tips AS jsonb),
                    :lead_quality, :conversion_probability,
                    :talk_time_ratio,
                    :analyzed_at, :analysis_version, :created_at
                )
            """), {
                "id": analysis_id,
                "call_id": call_id,
                "tenant_id": tenant_id,
                "uwc_job_id": legacy_uwc_job_id,
                "sentiment_score": sentiment_score,
                "engagement_score": engagement_score,
                "coaching_tips": json.dumps(coaching_tips) if coaching_tips else None,
                "lead_quality": lead_quality,
                "conversion_probability": conversion_probability,
                "talk_time_ratio": talk_time_ratio,
                "analyzed_at": datetime.utcnow(),
                "analysis_version": analysis_result.get('analysis_version', 'legacy_v1'),
                "created_at": datetime.utcnow()
            })
            
            db.commit()
            logger.info(f"Stored legacy analysis results for call {call_id} (ID: {analysis_id})")
            
        except Exception as e:
            logger.error(f"Error storing analysis results: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _emit_analysis_event(self, call: Dict[str, Any], analysis_result: Dict[str, Any]):
        """Emit analysis event for real-time updates."""
        try:
            success = emit(
                event_name="call.analysis.completed",
                payload={
                    "call_id": call['call_id'],
                    "company_id": call['company_id'],
                    "sales_rep_id": call['sales_rep_id'],
                    "analysis_result": analysis_result
                },
                tenant_id=call['company_id'],
                user_id=call['sales_rep_id'],
                severity="info"
            )
            
            if success:
                logger.debug(f"Analysis event emitted for call {call['call_id']}")
            else:
                logger.warning(f"Failed to emit analysis event for call {call['call_id']}")
                
        except Exception as e:
            logger.error(f"Error emitting analysis event: {e}")
    
    async def get_call_analysis(self, call_id: int) -> Optional[Dict[str, Any]]:
        """Get analysis results for a specific call."""
        db = SessionLocal()
        try:
            result = db.execute(text("""
                SELECT * FROM call_analysis 
                WHERE call_id = :call_id
                ORDER BY analyzed_at DESC
                LIMIT 1
            """), {"call_id": call_id}).fetchone()
            
            if result:
                return dict(result._mapping)
            return None
            
        finally:
            db.close()
    
    async def get_sales_rep_performance(self, sales_rep_id: str, days: int = 30) -> Dict[str, Any]:
        """Get performance analysis for a sales rep over the specified period."""
        db = SessionLocal()
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Get analysis results for the sales rep
            results = db.execute(text("""
                SELECT 
                    ca.performance_score,
                    ca.call_metrics,
                    ca.coaching_recommendations,
                    ca.analyzed_at,
                    c.duration,
                    c.status
                FROM call_analysis ca
                JOIN calls c ON ca.call_id = c.call_id
                WHERE ca.sales_rep_id = :sales_rep_id
                AND ca.analyzed_at >= :since_date
                ORDER BY ca.analyzed_at DESC
            """), {"sales_rep_id": sales_rep_id, "since_date": since_date}).fetchall()
            
            if not results:
                return {"message": "No analysis data available"}
            
            # Calculate aggregate metrics
            scores = [r.performance_score.get('overall_score', 0) for r in results if r.performance_score]
            avg_score = sum(scores) / len(scores) if scores else 0
            
            # Count recommendations by category
            all_recommendations = []
            for result in results:
                if result.coaching_recommendations:
                    all_recommendations.extend(result.coaching_recommendations)
            
            recommendation_counts = {}
            for rec in all_recommendations:
                category = rec.get('category', 'unknown')
                recommendation_counts[category] = recommendation_counts.get(category, 0) + 1
            
            return {
                "sales_rep_id": sales_rep_id,
                "period_days": days,
                "total_calls_analyzed": len(results),
                "average_score": round(avg_score, 2),
                "recommendation_breakdown": recommendation_counts,
                "recent_analyses": [dict(r._mapping) for r in results[:5]]  # Last 5 analyses
            }
            
        finally:
            db.close()


# Global post-call analysis service instance
post_call_analysis_service = PostCallAnalysisService()




















