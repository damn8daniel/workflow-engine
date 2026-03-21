"""REST API endpoints for the encrypted variable/secret store."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decrypt_value, encrypt_value
from app.models.workflow import Variable
from app.schemas.workflow import (
    PaginatedResponse,
    VariableCreate,
    VariableResponse,
    VariableUpdate,
)

router = APIRouter(prefix="/variables", tags=["variables"])


@router.post("", response_model=VariableResponse, status_code=201)
async def create_variable(
    payload: VariableCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    existing = await db.execute(select(Variable).where(Variable.key == payload.key))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Variable already exists")

    variable = Variable(
        key=payload.key,
        encrypted_value=encrypt_value(payload.value),
        is_secret=payload.is_secret,
        description=payload.description,
    )
    db.add(variable)
    await db.flush()

    return _to_response(variable, payload.value, payload.is_secret)


@router.get("", response_model=PaginatedResponse)
async def list_variables(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    total = (await db.execute(select(func.count(Variable.id)))).scalar() or 0
    result = await db.execute(
        select(Variable)
        .order_by(Variable.key)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        _to_response(v, decrypt_value(v.encrypted_value), v.is_secret)
        for v in result.scalars().all()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{key}", response_model=VariableResponse)
async def get_variable(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(Variable).where(Variable.key == key))
    variable = result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    value = decrypt_value(variable.encrypted_value)
    return _to_response(variable, value, variable.is_secret)


@router.patch("/{key}", response_model=VariableResponse)
async def update_variable(
    key: str,
    payload: VariableUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(Variable).where(Variable.key == key))
    variable = result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")

    if payload.value is not None:
        variable.encrypted_value = encrypt_value(payload.value)
    if payload.is_secret is not None:
        variable.is_secret = payload.is_secret
    if payload.description is not None:
        variable.description = payload.description

    await db.flush()
    value = decrypt_value(variable.encrypted_value)
    return _to_response(variable, value, variable.is_secret)


@router.delete("/{key}", status_code=204)
async def delete_variable(
    key: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Variable).where(Variable.key == key))
    variable = result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    await db.delete(variable)


def _to_response(variable: Variable, value: str, is_secret: bool) -> dict[str, Any]:
    return {
        "id": variable.id,
        "key": variable.key,
        "value": "********" if is_secret else value,
        "is_secret": variable.is_secret,
        "description": variable.description,
        "created_at": variable.created_at,
        "updated_at": variable.updated_at,
    }
