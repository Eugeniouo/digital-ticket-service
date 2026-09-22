# query_service

This project was generated using fastapi_template.

## UV

This project uses uv. It's a modern dependency management
tool.

To run the project use this set of commands:

```bash
uv sync --locked
uv run -m query_service
```

Or with `just`:

```bash
just run
```

This will start the server on the configured host.

You can find swagger documentation at `/api/docs`.

You can read more about uv here: [https://docs.astral.sh/ruff/](https://docs.astral.sh/ruff/)

## Docker

You can start the project with docker using this command:

```bash
docker compose up --build
```

This command exposes the web application on port 8000, mounts current directory and enables autoreload.

But you have to rebuild image every time you modify `uv.lock` or `pyproject.toml` with this command:

```bash
docker compose build
```



## Project structure

```bash
$ tree backend
backend
├── query_service
│   ├── __main__.py      # Startup script. Starts uvicorn.
│   ├── application.py   # FastAPI application configuration.
│   ├── lifespan.py      # Actions to perform on startup and shutdown.
│   ├── settings.py      # Main configuration settings for project.
│   ├── log.py           # Logging configuration.
│   ├── api              # Package with all handlers.
│   │   └── router.py    # Main router.
│   ├── database         # SQLAlchemy session, models, utils.
│   ├── migrations       # Alembic migrations.
│   └── modules          # Feature modules (handlers, schemas, services, repositories, exceptions).
└── tests                # Tests for project.
    └── conftest.py      # Fixtures for all tests.
```



## Adding a feature

Copy `backend/query_service/modules/dummy` as a template.

1. Create `backend/query_service/modules/<feature>/` with:
  - `schema.py` — request/response DTOs;
  - `repository.py` — database access;
  - `service.py` — business logic;
  - `handler.py` — FastAPI router;
  - optional `exceptions.py`.
2. Add a SQLAlchemy model in `database/` and generate a migration if the table is new.
3. Export `router` from the module `__init__.py`.
4. Include it in `backend/query_service/api/router.py`.
5. Add tests under `backend/tests/`.



## Configuration

This application can be configured with environment variables.

Copy `.env.example` to `.env` in the repository root (`just env` does this if `.env` is missing)
and edit the values. `.env` is gitignored. 

All environment variables should start with "QUERY_SERVICE_" prefix.

For example if you see in your "backend/query_service/settings.py" a variable named like
`random_parameter`, you should provide the "QUERY_SERVICE_RANDOM_PARAMETER" 
variable to configure the value. This behaviour can be changed by overriding `env_prefix` property
in `query_service.settings.Settings`.

See `.env.example` for a starter file.

Staff sign-in is `POST /api/auth/signin`. The migrator creates a `root` account when bootstrap username and password are set and that username does not exist yet.

After `docker compose up` the catalog is empty: `GET /api/departments` returns `[]` until you seed it. With the API already listening on port 8000:

```bash
just seed
```

That calls the public HTTP API as `root` and creates two departments (`DEMO01`, `DEMO02`), services, windows with service bindings, department `admin` / `operator` accounts, and generated slots for today and tomorrow (Europe/Moscow). It is idempotent.

Demo staff logins are constants in `backend/query_service/seed_demo.py`. Password for all of them is `password`:

| username | role | department |
|---|---|---|
| `admin1` | admin | DEMO01 |
| `op1` | operator | DEMO01 |
| `admin2` | admin | DEMO02 |
| `op2` | operator | DEMO02 |

You can read more about BaseSettings class here: [https://pydantic-docs.helpmanual.io/usage/settings/](https://pydantic-docs.helpmanual.io/usage/settings/)

## Pre-commit

To install pre-commit simply run inside the shell:

```bash
pre-commit install
```

pre-commit is very useful to check your code before publishing it.
It's configured using .pre-commit-config.yaml file.

By default it runs:

- mypy (validates types);
- ruff (spots possible bugs);

You can read more about pre-commit here: [https://pre-commit.com/](https://pre-commit.com/)

## Migrations

If you want to migrate your database, you should run following commands:

```bash
# To run all migrations until the migration with revision_id.
alembic upgrade "<revision_id>"

# To perform all pending migrations.
alembic upgrade "head"
```



### Reverting migrations

If you want to revert migrations, you should run:

```bash
# revert all migrations up to: revision_id.
alembic downgrade <revision_id>

# Revert everything.
 alembic downgrade base
```



### Migration generation

To generate migrations you should run:

```bash
# For automatic change detection.
alembic revision --autogenerate

# For empty file generation.
alembic revision
```



## Running tests

If you want to run it in docker, simply run:

```bash
docker compose run --build --rm api pytest -vv .
docker compose down
```

For running tests on your local machine.

1. you need to start all aux services.

We can do so by using our `docker-compose.yaml` configuration. It already has everything we need.

```bash
docker compose up -d --wait db
```

1. Run tests.

```bash
pytest -vv .
```

