"""Pydantic schemas for request/response serialization."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.workflow import RunState, TaskState, TriggerType


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class TaskDefinition(BaseModel):
    task_id: str
    callable_name: str
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    max_retries: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 3600


class DAGDefinition(BaseModel):
    tasks: list[TaskDefinition]


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    dag_definition: DAGDefinition
    is_active: bool = True
    cron_schedule: str | None = None
    max_retries: int = 3
    retry_delay_seconds: int = 60
    default_timeout: int = 3600
    tags: dict[str, Any] | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    dag_definition: DAGDefinition | None = None
    is_active: bool | None = None
    cron_schedule: str | None = None
    max_retries: int | None = None
    retry_delay_seconds: int | None = None
    default_timeout: int | None = None
    tags: dict[str, Any] | None = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str | None
    dag_definition: dict[str, Any]
    is_active: bool
    cron_schedule: str | None
    max_retries: int
    retry_delay_seconds: int
    default_timeout: int
    tags: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Workflow Run
# ---------------------------------------------------------------------------


class WorkflowRunCreate(BaseModel):
    config: dict[str, Any] | None = None
    execution_date: datetime | None = None
    trigger_type: TriggerType = TriggerType.MANUAL


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_id: str
    state: RunState
    trigger_type: TriggerType
    config: dict[str, Any] | None
    execution_date: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Task Instance
# ---------------------------------------------------------------------------


class TaskInstanceResponse(BaseModel):
    id: str
    run_id: str
    task_id: str
    state: TaskState
    attempt_number: int
    max_retries: int
    celery_task_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    error_message: str | None
    log_output: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# XCom
# ---------------------------------------------------------------------------


class XComResponse(BaseModel):
    id: str
    task_instance_id: str
    key: str
    value: Any
    created_at: datetime

    model_config = {"from_attributes": True}


class XComCreate(BaseModel):
    key: str = "return_value"
    value: Any = None


# ---------------------------------------------------------------------------
# Variable / Secret
# ---------------------------------------------------------------------------


class VariableCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: str
    is_secret: bool = False
    description: str | None = None


class VariableUpdate(BaseModel):
    value: str | None = None
    is_secret: bool | None = None
    description: str | None = None


class VariableResponse(BaseModel):
    id: str
    key: str
    value: str | None = None  # None when secret is masked
    is_secret: bool
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


class ScheduleCreate(BaseModel):
    cron_expression: str = Field(..., min_length=1)
    is_active: bool = True


class ScheduleResponse(BaseModel):
    id: str
    workflow_id: str
    cron_expression: str
    is_active: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


class WebhookCreate(BaseModel):
    callback_url: str | None = None


class WebhookResponse(BaseModel):
    id: str
    workflow_id: str
    token: str
    callback_url: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------


class BackfillRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    interval: str = "1d"  # e.g. "1d", "1h"
    config: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
