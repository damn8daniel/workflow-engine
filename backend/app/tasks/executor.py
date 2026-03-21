"""Celery task that executes a single workflow task inside a worker."""

from __future__ import annotations

import asyncio
import importlib
import io
import logging
import sys
import traceback
from contextlib import redirect_stdout
from datetime import datetime, timezone
from typing import Any

from celery import Task as CeleryTask

from app.core.celery_app import celery_app
from app.core.database import async_session_factory
from app.models.workflow import TaskInstance, TaskState, XCom

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Built-in example callables (for demo / testing)
# ---------------------------------------------------------------------------

_BUILTIN_CALLABLES: dict[str, Any] = {}


def register_callable(name: str):
    """Decorator to register a callable for use in DAG definitions."""

    def wrapper(fn):
        _BUILTIN_CALLABLES[name] = fn
        return fn

    return wrapper


@register_callable("builtin.echo")
def echo_task(message: str = "hello", **kwargs: Any) -> dict[str, Any]:
    print(f"[echo] {message}")
    return {"echoed": message}


@register_callable("builtin.sleep")
def sleep_task(seconds: int = 5, **kwargs: Any) -> dict[str, Any]:
    import time
    print(f"[sleep] sleeping for {seconds}s")
    time.sleep(seconds)
    return {"slept": seconds}


@register_callable("builtin.fail")
def fail_task(message: str = "intentional failure", **kwargs: Any) -> None:
    raise RuntimeError(message)


@register_callable("builtin.add")
def add_task(a: int = 0, b: int = 0, **kwargs: Any) -> dict[str, Any]:
    result = a + b
    print(f"[add] {a} + {b} = {result}")
    return {"result": result}


def _resolve_callable(name: str):
    """Resolve a callable by dotted path or builtin name."""
    if name in _BUILTIN_CALLABLES:
        return _BUILTIN_CALLABLES[name]
    # Try importing a dotted path: "module.path:function" or "module.path.function"
    if ":" in name:
        module_path, func_name = name.rsplit(":", 1)
    elif "." in name:
        module_path, func_name = name.rsplit(".", 1)
    else:
        raise ImportError(f"Cannot resolve callable: {name}")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


async def _update_task_state(task_instance_id: str, **fields: Any) -> None:
    """Update a TaskInstance in the database."""
    async with async_session_factory() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(TaskInstance).where(TaskInstance.id == task_instance_id)
        )
        ti = result.scalar_one_or_none()
        if ti:
            for k, v in fields.items():
                setattr(ti, k, v)
            await db.commit()


async def _store_xcom(task_instance_id: str, key: str, value: Any) -> None:
    """Store an XCom value for a task instance."""
    async with async_session_factory() as db:
        xcom = XCom(
            task_instance_id=task_instance_id,
            key=key,
            value=value if isinstance(value, dict) else {"value": value},
        )
        db.add(xcom)
        await db.commit()


async def _on_complete(
    task_instance_id: str,
    success: bool,
    error_message: str | None,
    log_output: str | None,
) -> None:
    """Trigger the scheduler's post-task callback."""
    from app.services.scheduler import WorkflowScheduler

    async with async_session_factory() as db:
        await WorkflowScheduler.on_task_complete(
            db, task_instance_id, success, error_message, log_output
        )
        await db.commit()


def _run_async(coro):
    """Run an async coroutine from sync Celery worker context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------


class ExecuteTaskBase(CeleryTask):
    autoretry_for = ()  # We handle retries ourselves
    max_retries = 0


@celery_app.task(
    name="app.tasks.executor.execute_task",
    base=ExecuteTaskBase,
    bind=True,
    acks_late=True,
)
def execute_task(
    self: CeleryTask,
    *,
    run_id: str,
    task_instance_id: str,
    task_id: str,
    callable_name: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """Execute a single task callable, capture output, and report back."""
    args = args or []
    kwargs = kwargs or {}

    logger.info("Executing task %s (instance=%s)", task_id, task_instance_id)

    # Mark as RUNNING
    _run_async(
        _update_task_state(
            task_instance_id,
            state=TaskState.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
    )

    stdout_capture = io.StringIO()
    result: Any = None
    success = False
    error_message: str | None = None

    try:
        fn = _resolve_callable(callable_name)

        with redirect_stdout(stdout_capture):
            result = fn(*args, **kwargs)

        # Store XCom return value
        if result is not None:
            _run_async(_store_xcom(task_instance_id, "return_value", result))

        success = True
        logger.info("Task %s completed successfully", task_id)

    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        logger.error("Task %s failed: %s", task_id, exc)

    finally:
        log_output = stdout_capture.getvalue()
        _run_async(
            _on_complete(task_instance_id, success, error_message, log_output)
        )

    return {
        "task_id": task_id,
        "success": success,
        "result": result if isinstance(result, (dict, list, str, int, float, bool, type(None))) else str(result),
    }
