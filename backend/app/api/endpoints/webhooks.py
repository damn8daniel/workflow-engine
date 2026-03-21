"""REST API endpoints for webhook management and triggering."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.workflow import WebhookConfig, Workflow
from app.schemas.workflow import WebhookCreate, WebhookResponse, WorkflowRunResponse
from app.services.webhook_service import WebhookService

router = APIRouter(tags=["webhooks"])


@router.post(
    "/workflows/{workflow_id}/webhooks",
    response_model=WebhookResponse,
    status_code=201,
)
async def create_webhook(
    workflow_id: str,
    payload: WebhookCreate,
    db: AsyncSession = Depends(get_db),
) -> WebhookConfig:
    wf = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    if not wf.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")
    return await WebhookService.create_webhook(db, workflow_id, payload.callback_url)


@router.get(
    "/workflows/{workflow_id}/webhooks",
    response_model=list[WebhookResponse],
)
async def list_webhooks(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[WebhookConfig]:
    result = await db.execute(
        select(WebhookConfig).where(WebhookConfig.workflow_id == workflow_id)
    )
    return list(result.scalars().all())


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(WebhookConfig).where(WebhookConfig.id == webhook_id)
    )
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(wh)


@router.post("/webhooks/trigger/{token}", response_model=WorkflowRunResponse)
async def trigger_webhook(
    token: str,
    payload: dict[str, Any] | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    run = await WebhookService.trigger_by_token(db, token, payload)
    if not run:
        raise HTTPException(status_code=404, detail="Invalid or inactive webhook")
    return run
