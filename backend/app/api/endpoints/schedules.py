"""REST API endpoints for cron schedule management."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.workflow import Schedule, Workflow
from app.schemas.workflow import ScheduleCreate, ScheduleResponse

router = APIRouter(prefix="/workflows/{workflow_id}/schedules", tags=["schedules"])


@router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    workflow_id: str,
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
) -> Schedule:
    # Verify workflow exists
    wf = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    if not wf.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Validate cron expression
    if not croniter.is_valid(payload.cron_expression):
        raise HTTPException(status_code=422, detail="Invalid cron expression")

    now = datetime.now(timezone.utc)
    cron = croniter(payload.cron_expression, now)
    next_run = cron.get_next(datetime)

    schedule = Schedule(
        workflow_id=workflow_id,
        cron_expression=payload.cron_expression,
        is_active=payload.is_active,
        next_run_at=next_run,
    )
    db.add(schedule)
    await db.flush()
    return schedule


@router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Schedule]:
    result = await db.execute(
        select(Schedule).where(Schedule.workflow_id == workflow_id)
    )
    return list(result.scalars().all())


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    workflow_id: str,
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.workflow_id == workflow_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(schedule)


@router.patch("/{schedule_id}/toggle", response_model=ScheduleResponse)
async def toggle_schedule(
    workflow_id: str,
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
) -> Schedule:
    result = await db.execute(
        select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.workflow_id == workflow_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule.is_active = not schedule.is_active
    await db.flush()
    return schedule
