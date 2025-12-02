"""
Tasks CRUD endpoints.
"""
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.database import get_db
from app.middleware.rbac import require_role
from app.models.task import Task, TaskStatus, TaskAssignee, TaskSource
from app.schemas.domain import TaskSummary
from app.schemas.responses import APIResponse, ErrorCodes, create_error_response
from app.services.domain_events import emit_domain_event

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskListResponse(BaseModel):
    """Response for task listing."""
    tasks: List[TaskSummary] = Field(default_factory=list)
    total: int = Field(..., description="Total count matching filters")
    overdue_count: int = Field(0, description="Count of overdue tasks")


class TaskUpdateBody(BaseModel):
    """Request body for updating a task."""
    status: Optional[TaskStatus] = None
    due_at: Optional[datetime] = None
    assigned_to: Optional[TaskAssignee] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    notes: Optional[str] = Field(None, description="Additional notes (stored in task_metadata)")


class TaskCreateBody(BaseModel):
    """Request body for creating a task."""
    description: str = Field(..., description="Task description")
    assigned_to: TaskAssignee = Field(..., description="Who should complete this task")
    contact_card_id: Optional[str] = Field(None, description="Associated contact card")
    lead_id: Optional[str] = Field(None, description="Associated lead")
    appointment_id: Optional[str] = Field(None, description="Associated appointment")
    call_id: Optional[int] = Field(None, description="Associated call")
    due_at: Optional[datetime] = Field(None, description="When task is due")
    priority: Optional[str] = Field(None, description="Priority level (high/medium/low)")
    source: TaskSource = Field(TaskSource.MANUAL, description="Task source")


@router.get("", response_model=APIResponse[TaskListResponse])
@require_role("manager", "csr", "sales_rep")
async def list_tasks(
    request: Request,
    assignee_id: Optional[str] = Query(None, description="Filter by assignee (user ID)"),
    lead_id: Optional[str] = Query(None, description="Filter by lead ID"),
    contact_card_id: Optional[str] = Query(None, description="Filter by contact card ID"),
    status: Optional[str] = Query(None, description="Filter by status (open, completed, overdue, cancelled)"),
    overdue: Optional[bool] = Query(None, description="Filter by overdue status"),
    due_before: Optional[datetime] = Query(None, description="Filter tasks due before this date"),
    due_after: Optional[datetime] = Query(None, description="Filter tasks due after this date"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tasks to return"),
    offset: int = Query(0, ge=0, description="Number of tasks to skip"),
    db: Session = Depends(get_db),
) -> APIResponse[TaskListResponse]:
    """
    List tasks with optional filters.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "user_role", None)
    
    # Build query
    query = db.query(Task).filter(Task.company_id == tenant_id)
    
    # Filter by assignee (map user_id to TaskAssignee if needed)
    if assignee_id:
        # For now, we'll filter by a custom field if we add assignee_user_id
        # Otherwise, we need to map user roles to TaskAssignee
        # This is a simplification - in production, you might want assignee_user_id field
        pass  # TODO: Implement assignee filtering when we have assignee_user_id field
    
    # Filter by lead_id
    if lead_id:
        query = query.filter(Task.lead_id == lead_id)
    
    # Filter by contact_card_id
    if contact_card_id:
        query = query.filter(Task.contact_card_id == contact_card_id)
    
    # Filter by status
    if status:
        try:
            status_enum = TaskStatus(status.lower())
            query = query.filter(Task.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=create_error_response(
                    error_code=ErrorCodes.INVALID_REQUEST,
                    message=f"Invalid status: {status}",
                    details={"valid_statuses": [s.value for s in TaskStatus]},
                    request_id=getattr(request.state, "trace_id", None),
                ).dict(),
            )
    
    # Filter by due date range
    if due_before:
        query = query.filter(Task.due_at <= due_before)
    if due_after:
        query = query.filter(Task.due_at >= due_after)
    
    # Filter by overdue
    if overdue is not None:
        now = datetime.utcnow()
        if overdue:
            query = query.filter(
                and_(
                    Task.due_at < now,
                    Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
                )
            )
        else:
            query = query.filter(
                or_(
                    Task.due_at >= now,
                    Task.due_at.is_(None),
                    Task.status.in_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
                )
            )
    
    # Order by due_at (nulls last), then created_at
    query = query.order_by(
        Task.due_at.asc().nullslast(),
        Task.created_at.desc()
    )
    
    # Get total count before pagination
    total_count = query.count()
    
    # Calculate overdue count (before pagination to get accurate count)
    now = datetime.utcnow()
    overdue_query = query.filter(
        and_(
            Task.due_at < now,
            Task.status.notin_([TaskStatus.COMPLETED, TaskStatus.CANCELLED])
        )
    )
    overdue_count = overdue_query.count()
    
    # Apply pagination
    tasks = query.offset(offset).limit(limit).all()
    
    # Build response
    task_summaries = [TaskSummary.from_orm(task) for task in tasks]
    
    response = TaskListResponse(
        tasks=task_summaries,
        total=total_count,
        overdue_count=overdue_count,
    )
    
    return APIResponse(data=response)


@router.patch("/{task_id}", response_model=APIResponse[TaskSummary])
@require_role("manager", "csr", "sales_rep")
async def update_task(
    request: Request,
    task_id: str,
    payload: TaskUpdateBody,
    db: Session = Depends(get_db),
) -> APIResponse[TaskSummary]:
    """
    Update a task.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.company_id == tenant_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Task not found",
                details={"task_id": task_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Update fields
    change_log = {}
    for field in ["status", "due_at", "assigned_to", "description", "priority"]:
        value = getattr(payload, field)
        if value is not None:
            old_value = getattr(task, field, None)
            setattr(task, field, value)
            if isinstance(value, datetime):
                change_log[field] = value.isoformat()
            elif hasattr(value, 'value'):  # Enum
                change_log[field] = value.value
            else:
                change_log[field] = value
    
    # Update notes in task_metadata
    if payload.notes is not None:
        import json
        metadata = {}
        if task.task_metadata:
            try:
                metadata = json.loads(task.task_metadata) if isinstance(task.task_metadata, str) else task.task_metadata
            except:
                metadata = {}
        metadata["notes"] = payload.notes
        task.task_metadata = json.dumps(metadata)
        change_log["notes"] = payload.notes
    
    # Auto-update status to OVERDUE if due_at has passed
    if task.due_at and task.due_at < datetime.utcnow():
        if task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            task.status = TaskStatus.OVERDUE
    
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    
    # Emit event
    emit_domain_event(
        event_name="task.updated",
        tenant_id=tenant_id,
        lead_id=task.lead_id,
        payload={
            "task_id": task.id,
            "company_id": task.company_id,
            "contact_card_id": task.contact_card_id,
            "changes": change_log,
        },
    )
    
    return APIResponse(data=TaskSummary.from_orm(task))


@router.post("/{task_id}/complete", response_model=APIResponse[TaskSummary])
@require_role("manager", "csr", "sales_rep")
async def complete_task(
    request: Request,
    task_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[TaskSummary]:
    """
    Mark a task as completed.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.company_id == tenant_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Task not found",
                details={"task_id": task_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Update task
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.utcnow()
    task.completed_by = user_id
    task.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(task)
    
    # Emit event
    emit_domain_event(
        event_name="task.completed",
        tenant_id=tenant_id,
        lead_id=task.lead_id,
        payload={
            "task_id": task.id,
            "company_id": task.company_id,
            "contact_card_id": task.contact_card_id,
            "completed_by": user_id,
            "completed_at": task.completed_at.isoformat(),
        },
    )
    
    return APIResponse(data=TaskSummary.from_orm(task))


@router.delete("/{task_id}", response_model=APIResponse[dict])
@require_role("manager", "csr", "sales_rep")
async def delete_task(
    request: Request,
    task_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """
    Soft delete a task (mark as cancelled).
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.company_id == tenant_id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=404,
            detail=create_error_response(
                error_code=ErrorCodes.NOT_FOUND,
                message="Task not found",
                details={"task_id": task_id},
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Soft delete: mark as cancelled
    task.status = TaskStatus.CANCELLED
    task.updated_at = datetime.utcnow()
    
    db.commit()
    
    # Emit event
    emit_domain_event(
        event_name="task.deleted",
        tenant_id=tenant_id,
        lead_id=task.lead_id,
        payload={
            "task_id": task.id,
            "company_id": task.company_id,
            "contact_card_id": task.contact_card_id,
        },
    )
    
    return APIResponse(data={"status": "deleted", "task_id": task_id})


@router.post("", response_model=APIResponse[TaskSummary])
@require_role("manager", "csr", "sales_rep")
async def create_task(
    request: Request,
    payload: TaskCreateBody,
    db: Session = Depends(get_db),
) -> APIResponse[TaskSummary]:
    """
    Create a new task.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    # Validate at least one entity is linked
    if not any([payload.contact_card_id, payload.lead_id, payload.appointment_id, payload.call_id]):
        raise HTTPException(
            status_code=400,
            detail=create_error_response(
                error_code=ErrorCodes.VALIDATION_ERROR,
                message="At least one of contact_card_id, lead_id, appointment_id, or call_id must be provided",
                request_id=getattr(request.state, "trace_id", None),
            ).dict(),
        )
    
    # Create task
    task = Task(
        id=str(uuid4()),
        company_id=tenant_id,
        contact_card_id=payload.contact_card_id,
        lead_id=payload.lead_id,
        appointment_id=payload.appointment_id,
        call_id=payload.call_id,
        description=payload.description,
        assigned_to=payload.assigned_to,
        source=payload.source,
        due_at=payload.due_at,
        priority=payload.priority,
        status=TaskStatus.OPEN,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Emit event
    emit_domain_event(
        event_name="task.created",
        tenant_id=tenant_id,
        lead_id=task.lead_id,
        payload={
            "task_id": task.id,
            "company_id": task.company_id,
            "contact_card_id": task.contact_card_id,
            "description": task.description,
            "assigned_to": task.assigned_to.value,
            "source": task.source.value,
        },
    )
    
    return APIResponse(data=TaskSummary.from_orm(task))

