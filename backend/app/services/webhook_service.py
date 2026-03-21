"""Webhook trigger and callback service."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key
from app.models.workflow import (
    RunState,
    WebhookConfig,
    Workflow,
    WorkflowRun,
)
from app.services.scheduler import WorkflowScheduler

logger = logging.getLogger(__name__)


class WebhookService:
    """Handles webhook creation, triggering, and completion callbacks."""

    @staticmethod
    async def create_webhook(
        db: AsyncSession,
        workflow_id: str,
        callback_url: str | None = None,
    ) -> WebhookConfig:
        webhook = WebhookConfig(
            workflow_id=workflow_id,
            token=generate_api_key(),
            callback_url=callback_url,
        )
        db.add(webhook)
        await db.flush()
        return webhook

    @staticmethod
    async def trigger_by_token(
        db: AsyncSession,
        token: str,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowRun | None:
        result = await db.execute(
            select(WebhookConfig).where(
                WebhookConfig.token == token,
                WebhookConfig.is_active.is_(True),
            )
        )
        webhook = result.scalar_one_or_none()
        if not webhook:
            return None

        wf_result = await db.execute(
            select(Workflow).where(Workflow.id == webhook.workflow_id)
        )
        workflow = wf_result.scalar_one_or_none()
        if not workflow or not workflow.is_active:
            return None

        run = await WorkflowScheduler.create_run(
            db,
            workflow,
            trigger_type="webhook",
            config=payload,
        )

        # Load workflow for dispatch
        run.workflow = workflow
        await WorkflowScheduler.dispatch_ready_tasks(db, run)

        return run

    @staticmethod
    async def send_completion_callback(run: WorkflowRun) -> None:
        """POST to the webhook callback_url when a run finishes."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(WebhookConfig).where(
                    WebhookConfig.workflow_id == run.workflow_id,
                    WebhookConfig.is_active.is_(True),
                )
            )
            webhooks = list(result.scalars().all())

        for wh in webhooks:
            if not wh.callback_url:
                continue
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    await client.post(
                        wh.callback_url,
                        json={
                            "run_id": run.id,
                            "workflow_id": run.workflow_id,
                            "state": run.state.value,
                            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                        },
                    )
            except Exception:
                logger.exception(
                    "Failed to send callback to %s", wh.callback_url
                )


# Re-import for the callback
from app.core.database import async_session_factory  # noqa: E402
