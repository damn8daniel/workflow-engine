"""SQLAlchemy ORM models for the workflow engine."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TaskState(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    SKIPPED = "skipped"
    UPSTREAM_FAILED = "upstream_failed"


class RunState(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerType(str, enum.Enum):
    MANUAL = "manual"
    CRON = "cron"
    WEBHOOK = "webhook"
    BACKFILL = "backfill"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Workflow(Base):
    """A workflow definition (DAG)."""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dag_definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    cron_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=60)
    default_timeout: Mapped[int] = mapped_column(Integer, default=3600)
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    runs: Mapped[list[WorkflowRun]] = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")
    schedules: Mapped[list[Schedule]] = relationship("Schedule", back_populates="workflow", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Workflow {self.name}>"


class WorkflowRun(Base):
    """A single execution of a workflow."""

    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    state: Mapped[RunState] = mapped_column(Enum(RunState), default=RunState.PENDING, index=True)
    trigger_type: Mapped[TriggerType] = mapped_column(Enum(TriggerType), default=TriggerType.MANUAL)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    workflow: Mapped[Workflow] = relationship("Workflow", back_populates="runs")
    task_instances: Mapped[list[TaskInstance]] = relationship(
        "TaskInstance", back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_workflow_runs_workflow_state", "workflow_id", "state"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowRun {self.id[:8]} state={self.state}>"


class TaskInstance(Base):
    """A single execution of one task within a workflow run."""

    __tablename__ = "task_instances"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[TaskState] = mapped_column(Enum(TaskState), default=TaskState.PENDING, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    run: Mapped[WorkflowRun] = relationship("WorkflowRun", back_populates="task_instances")
    xcom_values: Mapped[list[XCom]] = relationship("XCom", back_populates="task_instance", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("run_id", "task_id", "attempt_number", name="uq_task_instance_run_task_attempt"),
        Index("ix_task_instances_run_state", "run_id", "state"),
    )

    def __repr__(self) -> str:
        return f"<TaskInstance {self.task_id} state={self.state}>"


class XCom(Base):
    """Inter-task communication store (like Airflow XCom)."""

    __tablename__ = "xcoms"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    task_instance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("task_instances.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False, default="return_value")
    value: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task_instance: Mapped[TaskInstance] = relationship("TaskInstance", back_populates="xcom_values")

    __table_args__ = (
        UniqueConstraint("task_instance_id", "key", name="uq_xcom_task_key"),
    )


class Variable(Base):
    """Encrypted key-value store for workflow parameters and secrets."""

    __tablename__ = "variables"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Schedule(Base):
    """Cron schedule associated with a workflow."""

    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workflow: Mapped[Workflow] = relationship("Workflow", back_populates="schedules")


class WebhookConfig(Base):
    """Webhook endpoint configuration for triggering workflows."""

    __tablename__ = "webhook_configs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    workflow_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    callback_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
