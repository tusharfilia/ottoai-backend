"""
Mock UWC server for local testing.
Simulates UWC API responses based on Integration Checklist schemas.

Usage:
    python tests/mocks/uwc_mock_server.py

Then set:
    export UWC_BASE_URL=http://localhost:8001
    export UWC_API_KEY=mock_key
"""
from fastapi import FastAPI, Header, HTTPException, Request
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import uvicorn

mock_app = FastAPI(title="Mock UWC Server", version="1.0.0")


@mock_app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-uwc"}


@mock_app.post("/uwc/v1/asr/batch")
async def mock_asr_batch(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Mock ASR batch submission.
    
    Expected request:
    {
        "request_id": "req_123",
        "company_id": "tenant_123",
        "audio_urls": [
            {"url": "https://...", "call_id": "call_456"}
        ],
        "options": {"language": "en-US", ...}
    }
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    payload = await request.json()
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    return {
        "job_id": job_id,
        "status": "processing",
        "estimated_completion_sec": 30,
        "audio_count": len(payload.get("audio_urls", []))
    }


@mock_app.post("/uwc/v1/rag/query")
async def mock_rag_query(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Mock RAG query.
    
    Expected request:
    {
        "request_id": "req_123",
        "company_id": "tenant_123",
        "query": "What are the most common objections?",
        "context": {...},
        "options": {...}
    }
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    payload = await request.json()
    query = payload.get("query", "")
    
    # Generate contextual mock responses
    if "objection" in query.lower():
        answer = "The most common objection is 'price too high', occurring in 40% of calls this month. The second most common is 'need to get other quotes' at 36%."
        citations = [
            {
                "source": "calls",
                "id": "call_123",
                "title": "Call with John Smith - Price Objection",
                "url": "https://otto.ai/calls/call_123",
                "timestamp": "2025-10-05T14:30:00Z"
            },
            {
                "source": "analytics",
                "id": "objection_report_oct_2025",
                "title": "October 2025 Objection Analysis"
            }
        ]
    elif "rep" in query.lower() or "performance" in query.lower():
        answer = "Bradley Cohurst has the highest close rate at 65%, followed by Cole Ludewig at 42%. Bradley's strength is objection handling and agenda-setting."
        citations = [
            {
                "source": "analytics",
                "id": "rep_performance_2025_10",
                "title": "Rep Performance October 2025"
            }
        ]
    elif "coach" in query.lower() or "improve" in query.lower():
        answer = "Cole missed setting a clear agenda in 8 appointments this week, resulting in lower sit-down rates. Recommend coaching on agenda-setting and script adherence."
        citations = [
            {
                "source": "calls",
                "id": "call_789",
                "title": "Cole's appointment - Agenda missed",
                "url": "https://otto.ai/calls/call_789"
            }
        ]
    elif "follow" in query.lower():
        answer = "You have 15 warm leads ready for follow-up. Most are waiting on financing information or scheduling availability."
        citations = [
            {
                "source": "leads",
                "id": "lead_list_pending",
                "title": "Pending Follow-Ups"
            }
        ]
    else:
        answer = f"Mock answer for: {query}. This is a simulated response from the mock UWC server."
        citations = []
    
    return {
        "answer": answer,
        "citations": citations,
        "latency_ms": 250,
        "metadata": {
            "company_id": payload.get("company_id"),
            "query_tokens": len(query.split()),
            "model": "mock-llama-3.5"
        }
    }


@mock_app.post("/uwc/v1/documents/index")
async def mock_document_index(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Mock document indexing.
    
    Expected request:
    {
        "request_id": "req_123",
        "company_id": "tenant_123",
        "documents": [
            {"document_id": "doc_456", "content": "...", "metadata": {...}}
        ],
        "options": {...}
    }
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    payload = await request.json()
    documents = payload.get("documents", [])
    
    return {
        "job_id": f"doc_job_{uuid.uuid4().hex[:8]}",
        "status": "processing",
        "documents_count": len(documents),
        "estimated_completion_sec": len(documents) * 5
    }


@mock_app.post("/uwc/v1/training/submit")
async def mock_training_submit(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Mock training job submission.
    
    Expected request:
    {
        "request_id": "req_123",
        "company_id": "tenant_123",
        "training_data": {
            "rep_id": "rep_789",
            "media_urls": [...],
            "transcripts": [...]
        },
        "options": {...}
    }
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    payload = await request.json()
    training_data = payload.get("training_data", {})
    
    return {
        "job_id": f"train_{uuid.uuid4().hex[:8]}",
        "status": "queued",
        "rep_id": training_data.get("rep_id"),
        "estimated_completion_min": 120,
        "training_samples": len(training_data.get("media_urls", []))
    }


@mock_app.post("/uwc/v1/ai/followup/draft")
async def mock_followup_draft(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Mock follow-up draft generation.
    
    Expected request:
    {
        "company_id": "tenant_123",
        "rep_id": "rep_789",
        "lead_id": "lead_345",
        "context": {...},
        "channel": "sms"
    }
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    payload = await request.json()
    lead_id = payload.get("lead_id")
    channel = payload.get("channel", "sms")
    
    # Generate contextual draft
    if channel == "sms":
        draft = "Hi! Just following up on your roofing project. We have availability this week if you'd like to schedule. Let me know what works best for you!"
    else:
        draft = "Hello,\n\nI wanted to follow up on our conversation about your roofing project. We have some availability opening up this week and I'd love to help you move forward.\n\nLet me know what time works best for you.\n\nBest regards"
    
    return {
        "draft": draft,
        "tone": "friendly",
        "confidence": 0.91,
        "channel": channel,
        "lead_id": lead_id
    }


@mock_app.get("/uwc/v1/calls/{call_id}/analysis")
async def mock_get_analysis(
    call_id: str,
    authorization: Optional[str] = Header(None)
):
    """
    Mock ML analysis retrieval.
    
    Returns analysis results for a call.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return {
        "call_id": call_id,
        "status": "completed",
        "analysis": {
            "lead_classification": "qualified",
            "objections": ["price", "timeline", "need_other_quotes"],
            "sop_stage": "present",
            "sop_stages_completed": ["connect", "agenda", "assess", "report", "present"],
            "sop_stages_missed": ["ask", "finalize", "referral"],
            "rehash_score": 7.5,
            "coaching_tips": [
                "Set a clearer agenda at the start to improve sit-down rate",
                "Ask for the sale earlier - customer was ready but rep didn't close",
                "Request referrals before leaving the home"
            ],
            "strengths": ["Building rapport", "Product knowledge"],
            "weaknesses": ["Objection handling", "Closing"],
            "meeting_segments": [
                {"type": "introduction", "start_sec": 0, "end_sec": 75},
                {"type": "agenda", "start_sec": 75, "end_sec": 180},
                {"type": "assessment", "start_sec": 180, "end_sec": 420},
                {"type": "presentation", "start_sec": 420, "end_sec": 900},
                {"type": "objection_handling", "start_sec": 900, "end_sec": 1080}
            ]
        }
    }


@mock_app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Mock UWC Server",
        "version": "1.0.0",
        "endpoints": [
            "POST /uwc/v1/asr/batch",
            "POST /uwc/v1/rag/query",
            "POST /uwc/v1/documents/index",
            "POST /uwc/v1/training/submit",
            "POST /uwc/v1/ai/followup/draft",
            "GET /uwc/v1/calls/{call_id}/analysis"
        ],
        "note": "This is a mock server for testing. Replace with real UWC URL in production."
    }


if __name__ == "__main__":
    print("🚀 Starting Mock UWC Server on http://localhost:8001")
    print("📝 Set environment variables:")
    print("   export UWC_BASE_URL=http://localhost:8001")
    print("   export UWC_API_KEY=mock_key")
    print("")
    uvicorn.run(mock_app, host="0.0.0.0", port=8001, log_level="info")

