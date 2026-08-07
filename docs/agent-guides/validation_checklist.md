# Validation Checklist

## General
- [ ] Code compiles and runs
- [ ] All imports resolve — no circular imports
- [ ] Database migrations execute successfully
- [ ] API endpoints accessible and documented
- [ ] `api_contract.json` exists with all endpoints and `servers` array
- [ ] CORS allows `http://localhost:5173`
- [ ] `.env.example` `VITE_API_URL` matches actual backend URL
- [ ] Error responses use consistent format
- [ ] `docker-compose up` starts all services
- [ ] CRUD operations work through API

## Python-Specific
- [ ] `alembic upgrade head` runs: `cd backend && PYTHONPATH=. alembic upgrade head`
- [ ] `migrations/env.py` reads `DATABASE_URL` from `os.environ`
- [ ] No `from __future__ import annotations` in Pydantic files
- [ ] Response models use `model_config = {"from_attributes": True}`
- [ ] Async session uses `expire_on_commit=False`
- [ ] `Optional[X]` fields have `= None` default
- [ ] `datetime.now(timezone.utc)` used (not `datetime.utcnow()`)
- [ ] Enum columns use `values_callable`
- [ ] `backend/.dockerignore` exists
- [ ] `asyncio_mode = "auto"` in pytest config
- [ ] `requirements.txt` uses `psycopg[binary,asyncio]`
- [ ] Dockerfile CMD runs `alembic upgrade head` first
- [ ] Migrations use `postgresql.ENUM(create_type=False)`
