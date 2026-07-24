"""HTTP layer for Page Config Drafter — no session param, depends only on service."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.backend_implementation.page_config_drafter.schema import (
    ApprovalResponse,
    ApproveRequest,
    DeleteConfirmRequest,
    DeleteConfirmResponse,
    DeleteProposalResponse,
    DraftDiffResponse,
    DraftGenerateRequest,
    PageConfigResponse,
    RejectRequest,
    RejectionResponse,
    RollbackRequest,
    RollbackResponse,
)
from app.backend_implementation.page_config_drafter.service import (
    KGUnavailableError,
    PageConfigDrafterService,
    ParentConfigRequiredError,
    ProvenanceStoreUnavailableError,
)
from app.core.database import AsyncSessionLocal

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/page-config", tags=["page-config"])


async def get_service(request: Request) -> PageConfigDrafterService:
    async with AsyncSessionLocal() as session:
        yield PageConfigDrafterService(
            db=session,
            kg_client=request.app.state.kg_client,
            provenance_client=request.app.state.provenance_client,
        )


@router.post("/draft", response_model=PageConfigResponse, status_code=status.HTTP_201_CREATED)
async def generate_draft(
    body: DraftGenerateRequest,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.generate_draft(body)
    except KGUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ParentConfigRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except ProvenanceStoreUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.get("/draft/{draft_id}/diff", response_model=DraftDiffResponse)
async def get_draft_diff(
    draft_id: UUID,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.get_draft_diff(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/draft/{draft_id}/approve", response_model=ApprovalResponse)
async def approve_draft(
    draft_id: UUID,
    body: ApproveRequest,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.process_approval(draft_id, justification=body.justification)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ProvenanceStoreUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/draft/{draft_id}/reject", response_model=RejectionResponse)
async def reject_draft(
    draft_id: UUID,
    body: RejectRequest,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.process_rejection(draft_id, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ProvenanceStoreUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/{config_id}/rollback", response_model=RollbackResponse)
async def rollback_config(
    config_id: UUID,
    body: RollbackRequest,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.restore_from_provenance(config_id, body.version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ProvenanceStoreUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/{config_id}/delete-proposal", response_model=DeleteProposalResponse)
async def propose_deletion(
    config_id: UUID,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.build_deletion_diff_with_unwind(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ProvenanceStoreUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


@router.post("/{config_id}/delete-confirm", response_model=DeleteConfirmResponse)
async def confirm_deletion(
    config_id: UUID,
    body: DeleteConfirmRequest,
    service: PageConfigDrafterService = Depends(get_service),
):
    try:
        return await service.execute_confirmed_deletion(config_id, body.explicit_confirm)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except ProvenanceStoreUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
