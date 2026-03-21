"""REST API endpoints for workflow CRUD and execution."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.dsl.dag import DAG
from app.models.workflow import (
    TaskInstance,
    Workflow,
    WorkflowRun,
    XCom,
)
from app.schemas.workflow import (
    BackfillRequest,
    PaginatedResponse,
    TaskInstanceResponse,
    WorkflowCreate,
    WorkflowResponse,
    WorkflowRunCreate,
    WorkflowRunResponse,
    WorkflowUpdate,
    XComResponse,
)
from app.services.scheduler import WorkflowScheduler

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    # Validate DAG
    dag = DAG.from_dict(payload.name, payload.dag_definition.model_dump())
    errors = dag.validate()
    if errors:
        raise HTTPException(status_code=422, detail={"dag_errors": errors})

    workflow = Workflow(
        name=payload.name,
        description=payload.description,
        dag_definition=payload.dag_definition.model_dump(),
        is_active=payload.is_active,
        cron_schedule=payload.cron_schedule,
        max_retries=payload.max_retries,
        retry_delay_seconds=payload.retry_delay_seconds,
        default_timeout=payload.default_timeout,
        tags=payload.tags,
    )
    db.add(workflow)
    await db.flush()
    return workflow


@router.get("", response_model=PaginatedResponse)
async def list_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    query = select(Workflow)
    count_query = select(func.count(Workflow.id))
    if is_active is not None:
        query = query.where(Workflow.is_active == is_active)
        count_query = count_query.where(Workflow.is_active == is_active)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Workflow.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [WorkflowResponse.model_validate(w) for w in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "dag_definition" in update_data and update_data["dag_definition"] is not None:
        dag_data = update_data["dag_definition"]
        if hasattr(dag_data, "model_dump"):
            dag_data = dag_data.model_dump()
        dag = DAG.from_dict(workflow.name, dag_data)
        errors = dag.validate()
        if errors:
            raise HTTPException(status_code=422, detail={"dag_errors": errors})
        update_data["dag_definition"] = dag_data

    for field, value in update_data.items():
        setattr(workflow, field, value)

    await db.flush()
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(workflow)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@router.post("/{workflow_id}/runs", response_model=WorkflowRunResponse, status_code=201)
async def trigger_run(
    workflow_id: str,
    payload: WorkflowRunCreate | None = None,
    db: AsyncSession = Depends(get_db),
) -> WorkflowRun:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    payload = payload or WorkflowRunCreate()
    run = await WorkflowScheduler.create_run(
        db,
        workflow,
        trigger_type=payload.trigger_type.value,
        config=payload.config,
        execution_date=payload.execution_date,
    )

    # Dispatch initial tasks
    run.workflow = workflow
    await WorkflowScheduler.dispatch_ready_tasks(db, run)
    return run


@router.get("/{workflow_id}/runs", response_model=PaginatedResponse)
async def list_runs(
    workflow_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    count_q = select(func.count(WorkflowRun.id)).where(WorkflowRun.workflow_id == workflow_id)
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [WorkflowRunResponse.model_validate(r) for r in result.scalars().all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowRun:
    result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ---------------------------------------------------------------------------
# Task instances
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}/tasks", response_model=list[TaskInstanceResponse])
async def list_task_instances(
    run_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[TaskInstance]:
    result = await db.execute(
        select(TaskInstance)
        .where(TaskInstance.run_id == run_id)
        .order_by(TaskInstance.created_at)
    )
    return list(result.scalars().all())


@router.get("/tasks/{task_instance_id}", response_model=TaskInstanceResponse)
async def get_task_instance(
    task_instance_id: str,
    db: AsyncSession = Depends(get_db),
) -> TaskInstance:
    result = await db.execute(
        select(TaskInstance).where(TaskInstance.id == task_instance_id)
    )
    ti = result.scalar_one_or_none()
    if not ti:
        raise HTTPException(status_code=404, detail="Task instance not found")
    return ti


@router.get("/tasks/{task_instance_id}/logs")
async def get_task_logs(
    task_instance_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(
        select(TaskInstance).where(TaskInstance.id == task_instance_id)
    )
    ti = result.scalar_one_or_none()
    if not ti:
        raise HTTPException(status_code=404, detail="Task instance not found")
    return {
        "task_id": ti.task_id,
        "log_output": ti.log_output,
        "error_message": ti.error_message,
    }


# ---------------------------------------------------------------------------
# XCom
# ---------------------------------------------------------------------------


@router.get("/tasks/{task_instance_id}/xcom", response_model=list[XComResponse])
async def list_xcom(
    task_instance_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[XCom]:
    result = await db.execute(
        select(XCom).where(XCom.task_instance_id == task_instance_id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------


@router.post("/{workflow_id}/backfill", response_model=list[WorkflowRunResponse])
async def backfill_workflow(
    workflow_id: str,
    payload: BackfillRequest,
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowRun]:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    runs = await WorkflowScheduler.backfill(
        db,
        workflow,
        start_date=payload.start_date,
        end_date=payload.end_date,
        interval=payload.interval,
        config=payload.config,
    )

    # Dispatch tasks for each backfill run
    for run in runs:
        run.workflow = workflow
        await WorkflowScheduler.dispatch_ready_tasks(db, run)

    return runs
