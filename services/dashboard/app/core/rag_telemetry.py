"""
RAG telemetry tracking for Ask Otto feature.
Tracks groundedness, latency, cost, citations, and degraded mode for AI responses.
"""
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.rag_telemetry import RAGTelemetry
from app.obs.logging import get_logger
from app.obs.metrics import metrics

logger = get_logger(__name__)


class RAGTelemetryTracker:
    """Tracks RAG query telemetry for Ask Otto feature."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def track_query(
        self,
        tenant_id: str,
        user_id: str,
        user_role: str,
        query_text: str,
        answer_text: str,
        citations: List[Dict[str, Any]],
        latency_ms: float,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        groundedness_score: float,
        degraded_mode: bool = False,
        uwc_request_id: Optional[str] = None,
        fallback_used: bool = False
    ) -> RAGTelemetry:
        """
        Track a RAG query with full telemetry.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            user_role: User role (admin, csr, rep)
            query_text: Original query text
            answer_text: Generated answer
            citations: List of citations with metadata
            latency_ms: Query latency in milliseconds
            tokens_in: Input tokens consumed
            tokens_out: Output tokens generated
            cost_usd: Cost in USD
            groundedness_score: How well-grounded the answer is (0-1)
            degraded_mode: Whether degraded mode was used
            uwc_request_id: UWC request ID if applicable
            fallback_used: Whether fallback was used instead of UWC
            
        Returns:
            RAGTelemetry: Created telemetry record
        """
        try:
            # Calculate derived metrics
            citations_count = len(citations)
            avg_citation_score = sum(c.get('similarity_score', 0) for c in citations) / max(citations_count, 1)
            
            # Determine quality indicators
            has_citations = citations_count > 0
            is_grounded = groundedness_score >= 0.7
            is_high_quality = is_grounded and has_citations and not degraded_mode
            
            # Create telemetry record
            telemetry = RAGTelemetry(
                tenant_id=tenant_id,
                user_id=user_id,
                user_role=user_role,
                query_text=query_text[:1000],  # Truncate for storage
                answer_text=answer_text[:2000],  # Truncate for storage
                citations_count=citations_count,
                avg_citation_score=avg_citation_score,
                latency_ms=latency_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                groundedness_score=groundedness_score,
                degraded_mode=degraded_mode,
                fallback_used=fallback_used,
                uwc_request_id=uwc_request_id,
                has_citations=has_citations,
                is_grounded=is_grounded,
                is_high_quality=is_high_quality,
                created_at=datetime.utcnow()
            )
            
            self.db.add(telemetry)
            self.db.commit()
            self.db.refresh(telemetry)
            
            # Record Prometheus metrics
            self._record_metrics(
                tenant_id=tenant_id,
                user_role=user_role,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                groundedness_score=groundedness_score,
                citations_count=citations_count,
                degraded_mode=degraded_mode,
                fallback_used=fallback_used
            )
            
            logger.info(
                f"RAG telemetry recorded",
                extra={
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "latency_ms": latency_ms,
                    "cost_usd": cost_usd,
                    "groundedness_score": groundedness_score,
                    "citations_count": citations_count,
                    "degraded_mode": degraded_mode
                }
            )
            
            return telemetry
            
        except Exception as e:
            logger.error(f"Failed to record RAG telemetry: {str(e)}")
            self.db.rollback()
            raise
    
    def _record_metrics(
        self,
        tenant_id: str,
        user_role: str,
        latency_ms: float,
        cost_usd: float,
        groundedness_score: float,
        citations_count: int,
        degraded_mode: bool,
        fallback_used: bool
    ):
        """Record Prometheus metrics for RAG queries."""
        try:
            # Query count
            metrics.rag_queries_total.labels(
                tenant_id=tenant_id,
                user_role=user_role,
                degraded_mode=str(degraded_mode),
                fallback_used=str(fallback_used)
            ).inc()
            
            # Latency histogram
            metrics.rag_query_latency_ms.observe(latency_ms)
            
            # Cost tracking
            metrics.rag_query_cost_usd.observe(cost_usd)
            
            # Quality metrics
            metrics.rag_groundedness_score.observe(groundedness_score)
            metrics.rag_citations_count.observe(citations_count)
            
            # Degraded mode tracking
            if degraded_mode:
                metrics.rag_degraded_mode_total.labels(
                    tenant_id=tenant_id,
                    user_role=user_role
                ).inc()
            
            # Fallback usage tracking
            if fallback_used:
                metrics.rag_fallback_used_total.labels(
                    tenant_id=tenant_id,
                    user_role=user_role
                ).inc()
                
        except Exception as e:
            logger.error(f"Failed to record RAG metrics: {str(e)}")
    
    def get_tenant_metrics(
        self,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get aggregated RAG metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            days: Number of days to look back
            
        Returns:
            Dict containing aggregated metrics
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Query telemetry records
            records = self.db.query(RAGTelemetry).filter(
                RAGTelemetry.tenant_id == tenant_id,
                RAGTelemetry.created_at >= cutoff_date
            ).all()
            
            if not records:
                return {
                    "total_queries": 0,
                    "avg_latency_ms": 0,
                    "total_cost_usd": 0,
                    "avg_groundedness": 0,
                    "degraded_mode_rate": 0,
                    "fallback_rate": 0,
                    "high_quality_rate": 0
                }
            
            # Calculate aggregations
            total_queries = len(records)
            total_cost = sum(r.cost_usd for r in records)
            avg_latency = sum(r.latency_ms for r in records) / total_queries
            avg_groundedness = sum(r.groundedness_score for r in records) / total_queries
            
            degraded_count = sum(1 for r in records if r.degraded_mode)
            fallback_count = sum(1 for r in records if r.fallback_used)
            high_quality_count = sum(1 for r in records if r.is_high_quality)
            
            return {
                "total_queries": total_queries,
                "avg_latency_ms": round(avg_latency, 2),
                "total_cost_usd": round(total_cost, 4),
                "avg_groundedness": round(avg_groundedness, 3),
                "degraded_mode_rate": round(degraded_count / total_queries, 3),
                "fallback_rate": round(fallback_count / total_queries, 3),
                "high_quality_rate": round(high_quality_count / total_queries, 3)
            }
            
        except Exception as e:
            logger.error(f"Failed to get tenant RAG metrics: {str(e)}")
            return {}


def track_rag_query(
    db: Session,
    tenant_id: str,
    user_id: str,
    user_role: str,
    query_text: str,
    answer_text: str,
    citations: List[Dict[str, Any]],
    latency_ms: float,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    groundedness_score: float = 0.0,
    degraded_mode: bool = False,
    uwc_request_id: Optional[str] = None,
    fallback_used: bool = False
) -> RAGTelemetry:
    """
    Convenience function to track a RAG query.
    
    Args:
        db: Database session
        tenant_id: Tenant identifier
        user_id: User identifier
        user_role: User role
        query_text: Original query text
        answer_text: Generated answer
        citations: List of citations
        latency_ms: Query latency in milliseconds
        tokens_in: Input tokens consumed
        tokens_out: Output tokens generated
        cost_usd: Cost in USD
        groundedness_score: Groundedness score (0-1)
        degraded_mode: Whether degraded mode was used
        uwc_request_id: UWC request ID
        fallback_used: Whether fallback was used
        
    Returns:
        RAGTelemetry: Created telemetry record
    """
    tracker = RAGTelemetryTracker(db)
    return tracker.track_query(
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        query_text=query_text,
        answer_text=answer_text,
        citations=citations,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        groundedness_score=groundedness_score,
        degraded_mode=degraded_mode,
        uwc_request_id=uwc_request_id,
        fallback_used=fallback_used
    )

