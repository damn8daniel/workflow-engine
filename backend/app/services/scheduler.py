"""Workflow scheduler — orchestrates task execution with dependency awareness."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from croniter import croniter
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.dsl.dag import DAG
from app.models.workflow import (
    RunState,
    Schedule,
    TaskInstance,
    TaskState,
    Workflow,
    WorkflowRun,
)

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """Manages the lifecycle of workflow runs and task scheduling."""

    # ------------------------------------------------------------------
    # Run creation
    # ------------------------------------------------------------------

    @staticmethod
    async def create_run(
        db: AsyncSession,
        workflow: Workflow,
        trigger_type: str = "manual",
        config: dict[str, Any] | None = None,
        execution_date: datetime | None = None,
    ) -> WorkflowRun:
        """Create a new workflow run and its task instances."""
        run = WorkflowRun(
            workflow_id=workflow.id,
            trigger_type=trigger_type,
            config=config,
            execution_date=execution_date or datetime.now(timezone.utc),
        )
        db.add(run)
        await db.flush()

        dag = DAG.from_dict(workflow.name, workflow.dag_definition)
        for task_def in dag.tasks.values():
            ti = TaskInstance(
                run_id=run.id,
                task_id=task_def.task_id,
                state=TaskState.PENDING,
                max_retries=task_def.max_retries,
            )
            db.add(ti)

        await db.flush()
        return run

    # ------------------------------------------------------------------
    # Task dispatching
    # ------------------------------------------------------------------

    @staticmethod
    async def dispatch_ready_tasks(db: AsyncSession, run: WorkflowRun) -> list[str]:
        """Find tasks whose dependencies are met and enqueue them via Celery."""
        workflow = run.workflow
        dag = DAG.from_dict(workflow.name, workflow.dag_definition)

        # Fetch current task states
        result = await db.execute(
            select(TaskInstance).where(TaskInstance.run_id == run.id)
        )
        task_instances: list[TaskInstance] = list(result.scalars().all())
        state_map = {ti.task_id: ti for ti in task_instances}

        completed = {
            ti.task_id for ti in task_instances if ti.state == TaskState.SUCCESS
        }
        failed = {
            ti.task_id
            for ti in task_instances
            if ti.state in (TaskState.FAILED, TaskState.UPSTREAM_FAILED)
        }

        # Mark downstream of failures as UPSTREAM_FAILED
        for tid in list(failed):
            for child_id, child_task in dag.tasks.items():
                if tid in child_task.depends_on and child_id not in failed:
                    ti = state_map.get(child_id)
                    if ti and ti.state == TaskState.PENDING:
                        ti.state = TaskState.UPSTREAM_FAILED
                        failed.add(child_id)

        ready = dag.get_ready_tasks(completed)
        dispatched: list[str] = []

        for task_id in ready:
            ti = state_map.get(task_id)
            if not ti or ti.state not in (TaskState.PENDING, TaskState.RETRY):
                continue

            task_def = dag.tasks[task_id]
            ti.state = TaskState.QUEUED

            # Send to Celery
            celery_result = celery_app.send_task(
                "app.tasks.executor.execute_task",
                kwargs={
                    "run_id": run.id,
                    "task_instance_id": ti.id,
                    "task_id": task_id,
                    "callable_name": task_def.callable_name,
                    "args": task_def.args,
                    "kwargs": task_def.kwargs,
                    "timeout_seconds": task_def.timeout_seconds,
                },
                queue="default",
            )
            ti.celery_task_id = celery_result.id
            dispatched.append(task_id)

        await db.flush()

        # Update run state
        all_states = {ti.state for ti in task_instances}
        if all_states <= {TaskState.SUCCESS, TaskState.SKIPPED}:
            run.state = RunState.SUCCESS
            run.finished_at = datetime.now(timezone.utc)
            if run.started_at:
                run.duration_seconds = (run.finished_at - run.started_at).total_seconds()
        elif failed and not dispatched and not any(
            ti.state in (TaskState.QUEUED, TaskState.RUNNING) for ti in task_instances
        ):
            run.state = RunState.FAILED
            run.finished_at = datetime.now(timezone.utc)
            if run.started_at:
                run.duration_seconds = (run.finished_at - run.started_at).total_seconds()
        elif dispatched and run.state == RunState.PENDING:
            run.state = RunState.RUNNING
            run.started_at = datetime.now(timezone.utc)

        await db.flush()
        return dispatched

    # ------------------------------------------------------------------
    # Task completion callback
    # ------------------------------------------------------------------

    @staticmethod
    async def on_task_complete(
        db: AsyncSession,
        task_instance_id: str,
        success: bool,
        error_message: str | None = None,
        log_output: str | None = None,
    ) -> None:
        """Called when a Celery task finishes. Advances the DAG."""
        result = await db.execute(
            select(TaskInstance).where(TaskInstance.id == task_instance_id)
        )
        ti = result.scalar_one_or_none()
        if not ti:
            logger.error("TaskInstance %s not found", task_instance_id)
            return

        now = datetime.now(timezone.utc)
        ti.finished_at = now
        if ti.started_at:
            ti.duration_seconds = (now - ti.started_at).total_seconds()
        ti.log_output = log_output
        ti.error_message = error_message

        if success:
            ti.state = TaskState.SUCCESS
        elif ti.attempt_number < ti.max_retries:
            ti.state = TaskState.RETRY
            # Create a new attempt
            retry_ti = TaskInstance(
                run_id=ti.run_id,
                task_id=ti.task_id,
                state=TaskState.PENDING,
                attempt_number=ti.attempt_number + 1,
                max_retries=ti.max_retries,
            )
            db.add(retry_ti)
        else:
            ti.state = TaskState.FAILED

        await db.flush()

        # Load the run and dispatch next tasks
        run_result = await db.execute(
            select(WorkflowRun).where(WorkflowRun.id == ti.run_id)
        )
        run = run_result.scalar_one_or_none()
        if run:
            # Re-load workflow relationship
            wf_result = await db.execute(
                select(Workflow).where(Workflow.id == run.workflow_id)
            )
            run.workflow = wf_result.scalar_one()
            await WorkflowScheduler.dispatch_ready_tasks(db, run)

    # ------------------------------------------------------------------
    # Cron scheduler loop
    # ------------------------------------------------------------------

    @staticmethod
    async def run_cron_loop(poll_interval: int = 10) -> None:
        """Long-running loop that checks cron schedules and creates runs."""
        logger.info("Cron scheduler started (poll every %ds)", poll_interval)
        while True:
            try:
                async with async_session_factory() as db:
                    now = datetime.now(timezone.utc)
                    result = await db.execute(
                        select(Schedule).where(
                            Schedule.is_active.is_(True),
                            Schedule.next_run_at <= now,
                        )
                    )
                    schedules = list(result.scalars().all())

                    for schedule in schedules:
                        wf_result = await db.execute(
                            select(Workflow).where(Workflow.id == schedule.workflow_id)
                        )
                        workflow = wf_result.scalar_one_or_none()
                        if not workflow or not workflow.is_active:
                            continue

                        run = await WorkflowScheduler.create_run(
                            db,
                            workflow,
                            trigger_type="cron",
                            execution_date=schedule.next_run_at,
                        )
                        logger.info(
                            "Cron triggered run %s for workflow %s",
                            run.id,
                            workflow.name,
                        )

                        # Advance next_run_at
                        cron = croniter(schedule.cron_expression, now)
                        schedule.next_run_at = cron.get_next(datetime)
                        schedule.last_run_at = now

                        # Dispatch initial tasks
                        wf_result2 = await db.execute(
                            select(Workflow).where(Workflow.id == run.workflow_id)
                        )
                        run.workflow = wf_result2.scalar_one()
                        await WorkflowScheduler.dispatch_ready_tasks(db, run)

                    await db.commit()
            except Exception:
                logger.exception("Error in cron scheduler loop")

            await asyncio.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Backfill
    # ------------------------------------------------------------------

    @staticmethod
    async def backfill(
        db: AsyncSession,
        workflow: Workflow,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
        config: dict[str, Any] | None = None,
    ) -> list[WorkflowRun]:
        """Create runs for a historical date range."""
        delta = _parse_interval(interval)
        runs: list[WorkflowRun] = []
        current = start_date

        while current <= end_date:
            run = await WorkflowScheduler.create_run(
                db,
                workflow,
                trigger_type="backfill",
                config=config,
                execution_date=current,
            )
            runs.append(run)
            current += delta

        return runs


def _parse_interval(interval: str) -> timedelta:
    """Parse a simple interval string like '1d', '6h', '30m'."""
    unit = interval[-1]
    value = int(interval[:-1])
    match unit:
        case "d":
            return timedelta(days=value)
        case "h":
            return timedelta(hours=value)
        case "m":
            return timedelta(minutes=value)
        case _:
            raise ValueError(f"Unknown interval unit: {unit}")
