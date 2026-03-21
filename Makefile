.PHONY: up down build logs api worker frontend seed test lint

# Docker
up:
	cd docker && docker compose up --build -d

down:
	cd docker && docker compose down

logs:
	cd docker && docker compose logs -f

# Development
api:
	cd backend && uvicorn app.main:app --reload --port 8000

worker:
	cd backend && celery -A app.core.celery_app:celery_app worker --loglevel=info --concurrency=4

frontend:
	cd frontend && npm run dev

seed:
	python scripts/seed_example.py

# Quality
test:
	cd backend && pytest -v --cov=app

lint:
	cd backend && ruff check . && ruff format --check .
