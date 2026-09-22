[group("dev")]
default:
  @just --list

# copy .env.example when .env is missing
[group("dev")]
env:
    test -f .env || cp .env.example .env

# start Postgres and Valkey
[group("dev")]
db:
    docker compose up -d --wait db valkey

# stop Compose and delete volumes
[group("deploy")]
down:
    docker compose down -v

# apply Alembic migrations
[group("db")]
migrate:
    uv run alembic upgrade head

# Revert Alembic migrations (default: all)
[group("db")]
downgrade rev="base":
    uv run alembic downgrade {{rev}}

# create root staff from .env
[group("db")]
bootstrap:
    just env
    uv run -m query_service.bootstrap_staff

# load demo data
[group("db")]
seed:
    just env
    uv run -m query_service.seed_demo

# reset DB and apply migrations
[group("db")]
fresh:
    just env
    just down
    just db
    just migrate
    just bootstrap

# run API
[group("dev")]
serve:
    uv sync --locked
    QUERY_SERVICE_RELOAD=True uv run -m query_service

# setup Local API: env, DB, Valkey, migrate, bootstrap, serve
[group("dev")]
run-be:
    just env
    just db
    just migrate
    just bootstrap
    just serve

# celery worker
[group("dev")]
worker:
    uv run celery -A query_service.celery_app worker -l INFO

# celery beat
[group("dev")]
beat:
    uv run celery -A query_service.celery_app beat -l INFO --schedule /tmp/celerybeat-schedule

# frontend dev server (http://localhost:4173)
[group("dev")]
frontend:
    npm --prefix frontend run dev

# frontend production build
[group("deploy")]
frontend-build:
    npm --prefix frontend run build

# full stack: API, frontend, proxy, workers
[group("deploy")]
run:
    just env
    docker compose up --build

# vps overlay
[group("deploy")]
prod:
    just env
    docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build

# generate migrations
[group("db")]
gen_migrations message:
    just fresh
    uv run alembic revision --autogenerate -m "{{message}}"

# backend tests
[group("testing")]
test-be *args:
    uv run pytest {{args}}

# frontend tests
[group("testing")]
test-fe:
    npm --prefix frontend test

# backend and frontend tests
[group("testing")]
test:
    just test-be
    just test-fe

# wipe DB with tests
[group("testing")]
test-fresh:
    just fresh
    uv run pytest

# format code
[group("testing")]
fmt:
    uv run ruff format backend
    uv run ruff check backend --fix

# lint code
[group("testing")]
lint:
    uv run ruff check backend/query_service backend/tests
    uv run mypy backend/query_service backend/tests

# install pre-commit
[group("testing")]
hooks:
    uv run pre-commit install

# join PSQL client
[group("deploy")]
psql:
    docker compose exec db psql -U query_service -d query_service

# observe logs of a given service
[group("deploy")]
logs *svc:
    docker compose logs -f {{svc}}
