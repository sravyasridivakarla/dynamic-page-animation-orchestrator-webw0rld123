# CLAUDE.md

## Project: Page Config Drafter

**Tech Stack:** Context
**Scaffold Type:** Backend service

## Scaffold Structure

```
  backend/
  backend/app/
  backend/app/core/
  backend/tests/
  backend/tests/unit/
  backend/migrations/
  scripts/
  docs/
  docs/agent-guides/
```

## Module Pattern

Each feature gets its own subdirectory under the capability folder:

| File | Location |
|------|----------|
| `models.py` | `backend/app/`backend/<feature>/` |
| `schema.py` | `backend/app/`backend/<feature>/` |
| `repository.py` | `backend/app/`backend/<feature>/` |
| `service.py` | `backend/app/`backend/<feature>/` |
| `api.py` | `backend/app/`backend/<feature>/` |
| `__init__.py` | `backend/app/`backend/<feature>/` |
| `test_*_service.py` | `backend/tests/unit/` |

Each feature folder has short file names (`models.py`, not `feature_models.py`).

## Conventions

- **Naming Style:** `snake_case for all files and folders`
- **Layout:** `feature subdirectories under backend/app/ capability folder (backend/app/{cap}/feature_name/models.py)`
- **Test Pattern:** `test_*.py`
- **Model Pattern:** `<feature>/models.py`
- **Schema Pattern:** `<feature>/schema.py`
- **Api Pattern:** `<feature>/api.py`
- **Service Pattern:** `<feature>/service.py`
- **Repository Pattern:** `<feature>/repository.py`
- **Reference Doc:** `CONVENTIONS.md at project root`

## Reference

See `CONVENTIONS.md` at the project root for the full 6-file module
pattern, naming conventions, import patterns, and code snippets.

## Reference Guides

The `docs/agent-guides/` directory contains critical implementation references:

| File | Contents |
|------|----------|
| `python_patterns.md` | Async SQLAlchemy, Pydantic v2, Alembic pitfalls |
| `docker_compose_reference.md` | Docker Compose template and networking rules |
| `validation_checklist.md` | Post-implementation verification checklist |
| `api_contract_spec.md` | OpenAPI 3.0 contract format specification |
| `claude_md_template.md` | CLAUDE.md required sections and format |

**Read these files before implementing.** They contain fixes for common
runtime failures (MissingGreenlet, PydanticSchemaGenerationError, etc.).

## Project Overview

Page Config Drafter — backend agent pipeline that automates creation, update, and deletion of product page configurations by reading context from the Knowledge Graph Service and presenting structured diffs for human approval before any persistence occurs.

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Alembic · httpx

## API Endpoint Reference

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|--------------|----------|
| POST | `/v1/page-configs/draft` | Generate create draft from KG | `{product_id}` | `DiffResponse` (CREATE) |
| POST | `/v1/page-configs/approve` | Approve pending draft and persist | `{approval_token, approved}` | `{id, status}` |
| GET | `/v1/page-configs/{config_id}` | Retrieve current config | — | `PageConfigResponse` |
| POST | `/v1/page-configs/{config_id}/draft` | Generate update draft | `{product_id}` | `DiffResponse` (UPDATE) |
| POST | `/v1/page-configs/{config_id}/delete-draft` | Generate delete draft | — | `DiffResponse` (DELETE) |
| POST | `/v1/page-configs/{config_id}/rollback` | Restore prior version | `{to_version}` | `{id, status}` |

All endpoints require `Authorization: Bearer <JWT>` header (DEC-ENT-1).

## Data Models

**PageConfig** (`page_configs`): id (UUID PK), product_id, page_title, meta_description, layout_type (STANDARD/HERO/MINIMAL), visibility_status (DRAFT/PUBLISHED/ARCHIVED), created_at, updated_at, created_by, updated_by.

**ScrollSection** (`scroll_sections`): id, config_id (FK CASCADE), position, heading, content, background_image_url.

**VisualRepresentation** (`visual_representations`): id, config_id (FK CASCADE), type (IMAGE/VIDEO/CAROUSEL), url, alt_text, position.

**SourcingTimelineEvent** (`sourcing_timeline_events`): id, config_id (FK CASCADE), timestamp, event_type, description.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL URL (`postgresql+psycopg://user:pass@db:5432/dbname`) |
| `KG_SERVICE_URL` | Base URL for Knowledge Graph Service |
| `PROVENANCE_URL` | Base URL for Provenance & Trace Store |
| `APP_ENV` | Environment (default: development) |
| `APP_PORT` | Listen port (default: 8000) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Docker Compose PostgreSQL vars |

**DEC-SEC-9 conflict:** `psycopg[binary,asyncio]` is required for async PostgreSQL but is not on the approved allowlist. Add it to DEC-SEC-9 before deploying.

## Running the Service

```bash
# Development (from backend/)
cd backend && uvicorn app.main:app --reload

# Run tests (from backend/)
cd backend && pytest tests/ -v

# Run migrations
cd backend && PYTHONPATH=. alembic upgrade head

# Docker
docker-compose up -d
```

## Database

- **Type:** PostgreSQL 16
- **ORM:** SQLAlchemy 2.0 async with `expire_on_commit=False`
- **Migrations:** Alembic — `cd backend && PYTHONPATH=. alembic upgrade head`
- **Schema:** 4 tables with CASCADE DELETE from parent → children; 3 PostgreSQL enum types.

## Path Mappings

| Artifact Path | Scaffold Location |
|---|---|
| `backend/app/main.py` | `backend/app/`backend/main.py` |

<!-- arqence:decisions:begin -->
## Organization Decisions

These are settled, organization-wide engineering decisions. Every
change in this repository must comply with them. If one blocks your
work, surface the conflict instead of contradicting it.

- [DEC-BAK-48] Layered Module Boundaries for Agent Services: API modules must not reach into persistence internals. Data access goes through the service layer so storage can change without breaking the API surface.
- [DEC-ENT-1] Security: JWT validated at the edge: Every externally reachable endpoint requires a JWT validated at the gateway; no unauthenticated business endpoints.
- [DEC-SEC-9] Approved Python Dependency Allowlist for Agent Services: Generated agent services may only depend on Python packages vetted for supply chain risk. Adding a dependency means updating this decision, not installing ad hoc.

Anything not listed here: read .claude/rules/decision-index.md, or query lp_get_relevant_decisions / lp_get_decision by id.
<!-- arqence:decisions:end -->
