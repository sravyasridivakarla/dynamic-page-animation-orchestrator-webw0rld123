"""Page Config Drafter service entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.kg_client import KnowledgeGraphClient
from app.clients.provenance_client import ProvenanceStoreClient
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.kg_client = KnowledgeGraphClient(base_url=settings.KG_SERVICE_URL)
    app.state.provenance_client = ProvenanceStoreClient(base_url=settings.PROVENANCE_STORE_URL)
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

from app.backend_implementation.page_config_drafter.api import router as page_config_router  # noqa: E402

app.include_router(page_config_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "dynamic_page_animation_orchestrator_webw0rld"}
