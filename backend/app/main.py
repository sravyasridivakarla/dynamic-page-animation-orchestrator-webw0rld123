"""Page Config Drafter service entry point."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.backend_implementation.page_config_drafter.api import router as page_config_router
from app.backend_implementation.page_config_drafter.exceptions import (
    ConfigNotFoundError,
    InvalidDraftStateError,
    KnowledgeGraphUnavailableError,
    ParentNotFoundError,
    ProvenanceStoreUnavailableError,
)
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings.validate()
    application.state.kg_client = httpx.AsyncClient(
        base_url=settings.KG_SERVICE_URL,
        timeout=30.0,
    )
    application.state.provenance_client = httpx.AsyncClient(
        base_url=settings.PROVENANCE_URL,
        timeout=30.0,
    )
    logger.info("HTTP clients initialized")
    yield
    await application.state.kg_client.aclose()
    await application.state.provenance_client.aclose()
    logger.info("HTTP clients closed")


app = FastAPI(title="Page Config Drafter", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ConfigNotFoundError)
async def config_not_found_handler(request: Request, exc: ConfigNotFoundError):
    return JSONResponse(status_code=404, content={"error": str(exc), "code": "CONFIG_NOT_FOUND"})


@app.exception_handler(KnowledgeGraphUnavailableError)
async def kg_unavailable_handler(request: Request, exc: KnowledgeGraphUnavailableError):
    return JSONResponse(
        status_code=503,
        content={"error": str(exc), "code": "KG_UNAVAILABLE"},
    )


@app.exception_handler(ProvenanceStoreUnavailableError)
async def provenance_unavailable_handler(
    request: Request, exc: ProvenanceStoreUnavailableError
):
    return JSONResponse(
        status_code=503,
        content={"error": str(exc), "code": "PROVENANCE_UNAVAILABLE"},
    )


@app.exception_handler(InvalidDraftStateError)
async def invalid_draft_state_handler(request: Request, exc: InvalidDraftStateError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "code": "INVALID_DRAFT_STATE"},
    )


@app.exception_handler(ParentNotFoundError)
async def parent_not_found_handler(request: Request, exc: ParentNotFoundError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "code": "PARENT_NOT_FOUND"},
    )


app.include_router(page_config_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "page-config-drafter"}
