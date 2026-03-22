.PHONY: dev stop test migrate pipeline install lint

# Start all services (Redis + backend + Celery worker)
dev:
	docker compose up --build

# Stop all services
stop:
	docker compose down

# Install Python dependencies
install:
	cd backend && pip install -e ".[dev]"

# Run backend tests
test:
	cd backend && pytest -v --cov=app --cov=pipeline

# Run Alembic migrations
migrate:
	cd backend && alembic upgrade head

# Trigger a manual Celery satellite pipeline run
# Usage: make pipeline FIELD_ID=<uuid>
pipeline:
	cd backend && celery -A pipeline.celery_app call pipeline.tasks.run_harvest_agent \
		--args='["$(FIELD_ID)"]'

# Start backend dev server directly (without Docker)
serve:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery worker directly (without Docker)
worker:
	cd backend && celery -A pipeline.celery_app worker --loglevel=info

# Lint
lint:
	cd backend && ruff check . && ruff format --check .
