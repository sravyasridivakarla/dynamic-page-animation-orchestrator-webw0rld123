# Docker Compose Reference

## Required Services
1. **Database** (e.g. `db`): healthcheck with `start_period: 10s`, non-default host ports (5440:5432), named volume
2. **Backend**: build from `./backend`, `DATABASE_URL` uses service name (not localhost), `depends_on: service_healthy`
3. **Migrate**: runs `alembic upgrade head` once, `restart: "no"`, backend depends on `service_completed_successfully`

## Networking Rules
- Services reference each other by **service name** (e.g. `db:5432`)
- `localhost` inside a container = THAT container only
- Do NOT include obsolete `version: "3.8"` key

## Example
```yaml
services:
  db:
    image: postgres:16
    environment: {POSTGRES_USER: postgres, POSTGRES_PASSWORD: postgres, POSTGRES_DB: mydb}
    ports: ["5440:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 20
      start_period: 10s
  migrate:
    build: {context: ./backend}
    command: ["alembic", "upgrade", "head"]
    environment: {DATABASE_URL: "postgresql+psycopg://postgres:postgres@db:5432/mydb"}
    depends_on: {db: {condition: service_healthy}}
    restart: "no"
  backend:
    build: {context: ./backend}
    ports: ["8000:8000"]
    environment: {DATABASE_URL: "postgresql+psycopg://postgres:postgres@db:5432/mydb"}
    depends_on: {migrate: {condition: service_completed_successfully}}
    volumes: [./backend:/app]
volumes:
  pgdata:
```
