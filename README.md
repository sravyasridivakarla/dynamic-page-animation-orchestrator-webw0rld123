# Page Config Drafter

## Setup

1. Copy `.env.example` to `.env` and configure
2. Install dependencies: `pip install -r backend/requirements.txt`
3. Run: `cd backend && uvicorn app.main:app --reload`

## Docker

```bash
docker-compose up -d
```

## Project Structure

- `backend/` — All backend code (app, tests, migrations)
- `docs/` — Architecture documentation
- `scripts/` — Utility scripts

See `CONVENTIONS.md` at the project root for the 6-file module pattern.
