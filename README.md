# Distributed Workflow Engine

A production-grade distributed workflow engine built with Python, inspired by Apache Airflow but designed for simplicity and modern async patterns.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   React UI   │────▶│  FastAPI      │────▶│  PostgreSQL  │
│  (React Flow)│     │  REST API     │     │  (async)     │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐     ┌──────────────┐
                     │   Scheduler  │────▶│    Redis      │
                     │   (in-proc)  │     │   (broker)    │
                     └──────────────┘     └──────┬───────┘
                                                  │
                                          ┌──────▼───────┐
                                          │ Celery Workers│
                                          │ (N parallel)  │
                                          └──────────────┘
```

## Features

- **DAG Definition** — Python DSL with `>>` operator for chaining tasks
- **Dependency-Aware Scheduling** — topological sort with parallel execution of independent tasks
- **Celery Workers** — distributed task execution with configurable concurrency
- **Retry Logic** — configurable retries with exponential backoff per task
- **Cron Scheduling** — periodic workflow execution via cron expressions
- **Task State Machine** — `pending → queued → running → success/failed/retry`
- **React Dashboard** — DAG visualization with react-flow, run history, live logs
- **REST API** — full CRUD, trigger runs, backfill, manage schedules
- **Variables/Secrets** — Fernet-encrypted key-value store
- **Webhooks** — trigger workflows via HTTP token + completion callbacks
- **XCom** — inter-task data passing (return values stored as JSON)
- **Backfill** — re-run workflows for historical date ranges

## Quick Start

### Docker Compose (recommended)

```bash
cd docker
docker compose up --build
```

Services:
- **API**: http://localhost:8000 (Swagger docs at `/docs`)
- **Frontend**: http://localhost:3000
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Local Development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Celery worker (separate terminal)
celery -A app.core.celery_app:celery_app worker --loglevel=info

# Frontend
cd frontend
npm install
npm run dev
```

## DAG DSL Example

```python
from app.dsl.dag import DAG, Task

with DAG("etl_pipeline", cron_schedule="0 2 * * *") as dag:
    extract = Task(task_id="extract", callable_name="builtin.echo",
                   kwargs={"message": "Extracting..."})
    dag.add_task(extract)

    transform = Task(task_id="transform", callable_name="builtin.echo",
                     kwargs={"message": "Transforming..."})
    dag.add_task(transform)

    load = Task(task_id="load", callable_name="builtin.echo",
                kwargs={"message": "Loading..."})
    dag.add_task(load)

    extract >> transform >> load
```

## API Examples

```bash
# Create a workflow
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_pipeline",
    "dag_definition": {
      "tasks": [
        {"task_id": "step1", "callable_name": "builtin.echo", "kwargs": {"message": "hello"}, "depends_on": []},
        {"task_id": "step2", "callable_name": "builtin.add", "kwargs": {"a": 1, "b": 2}, "depends_on": ["step1"]}
      ]
    }
  }'

# Trigger a run
curl -X POST http://localhost:8000/api/v1/workflows/{id}/runs

# Check run status
curl http://localhost:8000/api/v1/workflows/runs/{run_id}

# View task logs
curl http://localhost:8000/api/v1/workflows/tasks/{task_instance_id}/logs

# Create a cron schedule
curl -X POST http://localhost:8000/api/v1/workflows/{id}/schedules \
  -H "Content-Type: application/json" \
  -d '{"cron_expression": "*/5 * * * *"}'

# Store a variable
curl -X POST http://localhost:8000/api/v1/variables \
  -H "Content-Type: application/json" \
  -d '{"key": "DB_HOST", "value": "prod-db.example.com", "is_secret": false}'

# Backfill
curl -X POST http://localhost:8000/api/v1/workflows/{id}/backfill \
  -H "Content-Type: application/json" \
  -d '{"start_date": "2024-01-01T00:00:00Z", "end_date": "2024-01-07T00:00:00Z", "interval": "1d"}'
```

## Project Structure

```
workflow-engine/
├── backend/
│   ├── app/
│   │   ├── api/endpoints/     # REST API routes
│   │   ├── core/              # Config, DB, Celery, security
│   │   ├── dsl/               # DAG/Task Python DSL
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Scheduler, webhook service
│   │   ├── tasks/             # Celery task executor
│   │   └── main.py            # FastAPI app entry point
│   ├── migrations/            # Alembic migrations
│   ├── tests/                 # Pytest suite
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/        # DAGVisualization, StateBadge
│   │   ├── pages/             # WorkflowList, WorkflowDetail, RunDetail
│   │   ├── api/               # Axios API client
│   │   └── App.tsx
│   └── Dockerfile
└── docker/
    └── docker-compose.yml
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI (async) |
| Task Queue | Celery + Redis |
| Database | PostgreSQL + SQLAlchemy 2.0 (async) |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| DAG Viz | @xyflow/react (React Flow) |
| Encryption | cryptography (Fernet) |
| Scheduling | croniter |
| Containers | Docker Compose |

## License

MIT
