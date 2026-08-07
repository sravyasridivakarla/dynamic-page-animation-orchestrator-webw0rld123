# CLAUDE.md

## Project: Page Config Drafter

**Tech Stack:** Python · FastAPI · SQLAlchemy (async) · PostgreSQL · Alembic · httpx
**Scaffold Type:** Backend service

## Project Overview

The Page Config Drafter is a backend agent pipeline that automates creation, updating, and deletion of product page configurations. It reads product catalog context from the Knowledge Graph Service and generates structured diffs for human review. A merchandiser approves or rejects each proposed change before anything is persisted — eliminating blank-form manual entry.

The system consolidates 12+ legacy use cases (LCDA-U30 through LCDA-U46) into a single agent-driven workflow. The draft lifecycle follows: **Knowledge Graph → Draft** (returned as structured diff) **→ Human Approval → Persist + Audit**.

## API Endpoint Reference

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|-------------|----------|
| POST | `/v1/page-configs/draft` | Generate a create draft from Knowledge Graph | `{ "product_id": "string" }` | `DiffResponse` (operation: CREATE) |
| POST | `/v1/page-configs/approve` | Approve a draft and persist to database | `{ "approval_token": "string", "approved": true }` | `{ "id": "UUID", "status": "PERSISTED" }` |
| GET | `/v1/page-configs/{config_id}` | Retrieve current state of a page config | — | `PageConfigDetailResponse` |
| POST | `/v1/page-configs/{config_id}/draft` | Generate an update draft for an existing config | `{ "product_id": "string" }` (optional) | `DiffResponse` (operation: UPDATE) |
| POST | `/v1/page-configs/{config_id}/delete-draft` | Generate a delete draft showing records to be removed | `{}` | `DiffResponse` (operation: DELETE) |
| POST | `/v1/page-configs/{config_id}/rollback` | Restore a prior config version from audit trail | `{ "to_version": "UUID" }` | `{ "id": "UUID", "status": "RESTORED" }` |
| GET | `/health` | Liveness probe | — | `{ "status": "healthy" }` |

**Authentication:** All business endpoints require `Authorization: Bearer <token>` header. Approval and rollback endpoints also require `X-User-ID: <actor_id>` header. JWT is validated at the gateway (DEC-ENT-1); the backend verifies header presence only.

## Data Models

### PageConfig (table: `page_configs`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Auto-generated unique identifier |
| `product_id` | String(255) | Foreign reference to product catalog |
| `page_title` | String(500) | Display title for the page |
| `meta_description` | Text | SEO meta description |
| `layout_type` | Enum | One of: `STANDARD`, `HERO`, `MINIMAL` |
| `visibility_status` | Enum | One of: `DRAFT`, `PUBLISHED`, `ARCHIVED` |
| `created_at` | DateTime (tz) | Creation timestamp (server default) |
| `updated_at` | DateTime (tz) | Last update timestamp (auto-updated) |
| `created_by` | String(255) | Actor ID of creator |
| `updated_by` | String(255) | Actor ID of last updater |

**Relationships:** one-to-many with `ScrollSection`, `VisualRepresentation`, `SourcingTimelineEvent` (all cascade delete).

### ScrollSection (table: `scroll_sections`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `config_id` | UUID (FK → page_configs) | Parent config, cascade delete |
| `position` | Integer | Order in the list |
| `heading` | String(500) | Section heading |
| `content` | Text | Section body text |
| `background_image_url` | String(2048) | URL to background image |
| `created_at` / `updated_at` | DateTime (tz) | Audit timestamps |

### VisualRepresentation (table: `visual_representations`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `config_id` | UUID (FK → page_configs) | Parent config, cascade delete |
| `type` | Enum | One of: `IMAGE`, `VIDEO`, `CAROUSEL` |
| `url` | String(2048) | Media URL |
| `alt_text` | String(500) | Accessibility alt text |
| `position` | Integer | Order in the list |
| `created_at` / `updated_at` | DateTime (tz) | Audit timestamps |

### SourcingTimelineEvent (table: `sourcing_timeline_events`)

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `config_id` | UUID (FK → page_configs) | Parent config, cascade delete |
| `timestamp` | DateTime (tz) | When the event occurred |
| `event_type` | String(255) | Event type (validated against Knowledge Graph) |
| `description` | Text | Event details |
| `created_at` / `updated_at` | DateTime (tz) | Audit timestamps |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | Async PostgreSQL URL: `postgresql+psycopg://user:pass@host:port/db` |
| `KG_SERVICE_URL` | Yes | — | Base URL for the Knowledge Graph Service |
| `PROVENANCE_URL` | Yes | — | Base URL for the Provenance & Trace Store |
| `CORS_ORIGINS` | No | `http://localhost:5173,http://localhost:3000` | Comma-separated list of allowed CORS origins |
| `APP_NAME` | No | `Page Config Drafter` | Application name |
| `APP_ENV` | No | `development` | Environment name |
| `APP_PORT` | No | `8000` | Listening port |

Copy `.env.example` to `.env` and fill in `DATABASE_URL`, `KG_SERVICE_URL`, and `PROVENANCE_URL`.

## Running the Service

```bash
# Install dependencies
cd backend && pip install -r requirements.txt

# Run database migrations
cd backend && PYTHONPATH=. alembic upgrade head

# Start development server (with auto-reload)
cd backend && uvicorn app.main:app --reload

# Run tests
cd backend && pytest tests/ -v

# Docker Compose (full stack)
docker-compose up -d
```

## Database

- **Type:** PostgreSQL 16
- **ORM:** SQLAlchemy 2 (async with psycopg3 driver)
- **Migrations:** Alembic (`backend/migrations/`)
- **Migration command:** `cd backend && PYTHONPATH=. alembic upgrade head`
- **Docker port:** `5440:5432` (host port 5440 → container port 5432)
- **Connection string format:** `postgresql+psycopg://user:pass@host:port/dbname`

### Schema Overview

Three ENUM types created by migration `001`:
- `layout_type`: STANDARD, HERO, MINIMAL
- `visibility_status`: DRAFT, PUBLISHED, ARCHIVED
- `visual_representation_type`: IMAGE, VIDEO, CAROUSEL

Four tables with cascade-delete relationships: `page_configs` → `scroll_sections`, `visual_representations`, `sourcing_timeline_events`.

## Module Structure

```
backend/app/backend_implementation/page_config_drafter/
    __init__.py          # Package init
    models.py            # SQLAlchemy ORM models (4 models + 3 enums)
    schema.py            # Pydantic request/response schemas
    exceptions.py        # Domain exceptions mapped to HTTP status codes
    repository.py        # Data access layer (PageConfigRepository)
    service.py           # Business logic (PageConfigService + _draft_store)
    api.py               # FastAPI router (6 endpoints + auth dependencies)
```

## Draft Store

Pending drafts are held in `service._draft_store` (module-level dict keyed by `approval_token`). This is intentionally in-memory and single-process. The draft is not persisted until `POST /v1/page-configs/approve` is called with `approved: true`.

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

## Commands

```bash
# Run service (from backend/ directory)
cd backend && uvicorn app.main:app --reload

# Run tests (from backend/ directory)
cd backend && pytest tests/ -v

# Docker
docker-compose up -d
```

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
