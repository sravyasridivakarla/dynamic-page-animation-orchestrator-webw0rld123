"""FastAPI router for page config drafter."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db

from .exceptions import (
    ConfigNotFoundError,
    InvalidDraftStateError,
    KnowledgeGraphUnavailableError,
    ParentNotFoundError,
    ProvenanceStoreUnavailableError,
)
from .repository import PageConfigRepository
from .schema import (
    ApproveRequest,
    ApproveResponse,
    CreateDraftRequest,
    DiffResponse,
    PageConfigResponse,
    RollbackRequest,
    RollbackResponse,
    ScrollSectionDraft,
    SourcingTimelineEventDraft,
    UpdateDraftRequest,
    VisualRepresentationDraft,
)
from .service import PageConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/page-configs", tags=["page-configs"])


def _build_service(req: Request, db: AsyncSession) -> PageConfigService:
    repo = PageConfigRepository(db)
    return PageConfigService(
        repo=repo,
        kg_client=req.app.state.kg_client,
        provenance_client=req.app.state.provenance_client,
        db=db,
    )


@router.post("/draft", response_model=DiffResponse)
async def create_draft(
    body: CreateDraftRequest,
    req: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = _build_service(req, db)
    try:
        return await service.generate_create_draft(body.product_id)
    except KnowledgeGraphUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.detail)


@router.post("/approve", response_model=ApproveResponse)
async def approve_draft(
    body: ApproveRequest,
    req: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_id = current_user.get("sub", "unknown")
    service = _build_service(req, db)
    try:
        config_id, approval_status = await service.approve_and_persist_draft(
            body.approval_token, body.approved, actor_id
        )
        return ApproveResponse(id=config_id, status=approval_status)
    except InvalidDraftStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)
    except ParentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)
    except ProvenanceStoreUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.detail)


@router.get("/{config_id}", response_model=PageConfigResponse)
async def get_config(
    config_id: uuid.UUID,
    req: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = _build_service(req, db)
    try:
        config = await service.repo.get_by_id(config_id)
        return PageConfigResponse(
            id=config.id,
            product_id=config.product_id,
            page_title=config.page_title,
            meta_description=config.meta_description,
            layout_type=config.layout_type,
            visibility_status=config.visibility_status,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
            updated_by=config.updated_by,
            scroll_sections=[
                ScrollSectionDraft(
                    id=s.id,
                    position=s.position,
                    heading=s.heading,
                    content=s.content,
                    background_image_url=s.background_image_url,
                )
                for s in config.scroll_sections
            ],
            visual_representations=[
                VisualRepresentationDraft(
                    id=v.id,
                    type=v.type,
                    url=v.url,
                    alt_text=v.alt_text,
                    position=v.position,
                )
                for v in config.visual_representations
            ],
            sourcing_timeline_events=[
                SourcingTimelineEventDraft(
                    id=e.id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    description=e.description,
                )
                for e in config.sourcing_timeline_events
            ],
        )
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail)


@router.post("/{config_id}/draft", response_model=DiffResponse)
async def update_draft(
    config_id: uuid.UUID,
    body: UpdateDraftRequest,
    req: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = _build_service(req, db)
    try:
        return await service.generate_update_draft(config_id, body.product_id)
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail)
    except KnowledgeGraphUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.detail)


@router.post("/{config_id}/delete-draft", response_model=DiffResponse)
async def delete_draft(
    config_id: uuid.UUID,
    req: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = _build_service(req, db)
    try:
        return await service.generate_delete_draft(config_id)
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail)


@router.post("/{config_id}/rollback", response_model=RollbackResponse)
async def rollback_config(
    config_id: uuid.UUID,
    body: RollbackRequest,
    req: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    actor_id = current_user.get("sub", "unknown")
    service = _build_service(req, db)
    try:
        restored_id, rollback_status = await service.rollback_to_version(
            config_id, body.to_version, actor_id
        )
        return RollbackResponse(id=restored_id, status=rollback_status)
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail)
    except ParentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)
    except ProvenanceStoreUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.detail)
