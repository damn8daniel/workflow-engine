"""Integration tests for the REST API (uses TestClient with in-memory SQLite)."""

from __future__ import annotations

import os

# Override DB before importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import Base, engine, init_db
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


SAMPLE_DAG = {
    "tasks": [
        {"task_id": "extract", "callable_name": "builtin.echo", "depends_on": []},
        {"task_id": "transform", "callable_name": "builtin.echo", "depends_on": ["extract"]},
        {"task_id": "load", "callable_name": "builtin.echo", "depends_on": ["transform"]},
    ]
}


class TestWorkflowCRUD:
    async def test_create_and_get(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "test-wf", "dag_definition": SAMPLE_DAG},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-wf"
        wf_id = data["id"]

        resp2 = await client.get(f"/api/v1/workflows/{wf_id}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "test-wf"

    async def test_list_workflows(self, client: AsyncClient):
        await client.post(
            "/api/v1/workflows",
            json={"name": "wf1", "dag_definition": SAMPLE_DAG},
        )
        await client.post(
            "/api/v1/workflows",
            json={"name": "wf2", "dag_definition": SAMPLE_DAG},
        )
        resp = await client.get("/api/v1/workflows")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_update_workflow(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "updatable", "dag_definition": SAMPLE_DAG},
        )
        wf_id = resp.json()["id"]
        resp2 = await client.patch(
            f"/api/v1/workflows/{wf_id}",
            json={"description": "Updated description"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["description"] == "Updated description"

    async def test_delete_workflow(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/workflows",
            json={"name": "deletable", "dag_definition": SAMPLE_DAG},
        )
        wf_id = resp.json()["id"]
        resp2 = await client.delete(f"/api/v1/workflows/{wf_id}")
        assert resp2.status_code == 204

    async def test_invalid_dag_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "bad-dag",
                "dag_definition": {
                    "tasks": [
                        {"task_id": "a", "callable_name": "x", "depends_on": ["b"]},
                        {"task_id": "b", "callable_name": "x", "depends_on": ["a"]},
                    ]
                },
            },
        )
        assert resp.status_code == 422


class TestVariables:
    async def test_create_and_get_variable(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/variables",
            json={"key": "DB_HOST", "value": "localhost"},
        )
        assert resp.status_code == 201
        assert resp.json()["key"] == "DB_HOST"
        assert resp.json()["value"] == "localhost"

    async def test_secret_variable_masked(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/variables",
            json={"key": "SECRET_TOKEN", "value": "abc123", "is_secret": True},
        )
        assert resp.status_code == 201
        assert resp.json()["value"] == "********"

    async def test_delete_variable(self, client: AsyncClient):
        await client.post(
            "/api/v1/variables",
            json={"key": "TEMP", "value": "val"},
        )
        resp = await client.delete("/api/v1/variables/TEMP")
        assert resp.status_code == 204


class TestHealth:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
