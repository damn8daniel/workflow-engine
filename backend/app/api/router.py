"""Central API router — aggregates all endpoint modules."""

from fastapi import APIRouter

from app.api.endpoints import schedules, variables, webhooks, workflows

api_router = APIRouter()

api_router.include_router(workflows.router)
api_router.include_router(variables.router)
api_router.include_router(schedules.router)
api_router.include_router(webhooks.router)
