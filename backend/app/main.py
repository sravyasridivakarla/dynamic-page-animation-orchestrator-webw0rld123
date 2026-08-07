"""Page Config Drafter service entry point."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.backend_implementation.page_config_drafter.api import router as page_config_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.kg_client = httpx.AsyncClient(
        base_url=settings.KG_SERVICE_URL,
        timeout=10.0,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    app.state.provenance_client = httpx.AsyncClient(
        base_url=settings.PROVENANCE_URL,
        timeout=10.0,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    yield
    await app.state.kg_client.aclose()
    await app.state.provenance_client.aclose()


app = FastAPI(title="Page Config Drafter", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(page_config_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "backend"}
