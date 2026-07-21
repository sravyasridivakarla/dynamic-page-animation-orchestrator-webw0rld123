"""FastAPI router for Page Config Drafter — HTTP concerns only."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

from .schema import (
    ApproveRequest,
    DeleteConfirmResponse,
    DeleteProposalResponse,
    DiffResponse,
    DraftRequest,
    PageConfigResponse,
    RejectRequest,
    RollbackResponse,
)
from .service import (
    InvalidStateError,
    KGUnavailableFallbackError,
    NotFoundError,
    PageConfigDrafterService,
    ProvenanceUnavailableError,
)

router = APIRouter(prefix="/v1/page-config", tags=["page-config"])


def get_service(request: Request, session: AsyncSession = Depends(get_db)) -> PageConfigDrafterService:
    return PageConfigDrafterService(
        session=session,
        kg_client=request.app.state.kg_client,
        provenance_client=request.app.state.provenance_client,
    )


@router.post("/draft", response_model=PageConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    body: DraftRequest,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        config = await service.generate_draft(body)
        return config
    except KGUnavailableFallbackError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "kg_unavailable",
                "message": str(exc),
                "fallback": "Use the legacy manual create-config form.",
            },
        )
    except ProvenanceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "provenance_unavailable", "message": str(exc)},
        )


@router.get("/draft/{draft_id}/diff", response_model=DiffResponse)
async def get_diff(
    draft_id: UUID,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.get_draft_diff(draft_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/draft/{draft_id}/approve", response_model=PageConfigResponse)
async def approve_draft(
    draft_id: UUID,
    body: ApproveRequest,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.process_approval(draft_id, body)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ProvenanceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "provenance_unavailable", "message": str(exc)},
        )


@router.post("/draft/{draft_id}/reject", response_model=PageConfigResponse)
async def reject_draft(
    draft_id: UUID,
    body: RejectRequest,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.process_rejection(draft_id, body)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ProvenanceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "provenance_unavailable", "message": str(exc)},
        )


@router.post("/{config_id}/rollback", response_model=RollbackResponse)
async def rollback_config(
    config_id: UUID,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.rollback_config(config_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ProvenanceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "provenance_unavailable", "message": str(exc)},
        )


@router.post("/{config_id}/delete-proposal", response_model=DeleteProposalResponse)
async def propose_deletion(
    config_id: UUID,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.propose_deletion(config_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ProvenanceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "provenance_unavailable", "message": str(exc)},
        )


@router.post("/{config_id}/delete-confirm", response_model=DeleteConfirmResponse)
async def confirm_deletion(
    config_id: UUID,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.execute_confirmed_deletion(config_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ProvenanceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "provenance_unavailable", "message": str(exc)},
        )
