"""FastAPI router for page config drafter endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session

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
    DiffResponse,
    GenerateCreateDraftRequest,
    GenerateUpdateDraftRequest,
    PageConfigDetailResponse,
    RollbackRequest,
    RollbackResponse,
)
from .service import PageConfigService

router = APIRouter(prefix="/v1/page-configs", tags=["page-config-drafter"])


async def require_auth(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    return authorization[7:]


async def get_actor_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-ID header",
        )
    return x_user_id


async def get_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> PageConfigService:
    repository = PageConfigRepository(session)
    return PageConfigService(
        session=session,
        repository=repository,
        kg_client=request.app.state.kg_client,
        provenance_client=request.app.state.provenance_client,
    )


def _handle_domain_exception(exc: Exception) -> HTTPException:
    mapping = {
        ConfigNotFoundError: 404,
        KnowledgeGraphUnavailableError: 503,
        ProvenanceStoreUnavailableError: 503,
        InvalidDraftStateError: 400,
        ParentNotFoundError: 400,
    }
    code = mapping.get(type(exc), 500)
    return HTTPException(status_code=code, detail=str(exc))


@router.post("/draft", response_model=DiffResponse, status_code=status.HTTP_200_OK)
async def create_draft(
    body: GenerateCreateDraftRequest,
    _: str = Depends(require_auth),
    service: PageConfigService = Depends(get_service),
) -> DiffResponse:
    try:
        return await service.generate_create_draft(body.product_id)
    except (
        KnowledgeGraphUnavailableError,
        InvalidDraftStateError,
        ParentNotFoundError,
    ) as exc:
        raise _handle_domain_exception(exc)


@router.post("/approve", response_model=ApproveResponse, status_code=status.HTTP_200_OK)
async def approve_draft(
    body: ApproveRequest,
    actor_id: str = Depends(get_actor_id),
    _: str = Depends(require_auth),
    service: PageConfigService = Depends(get_service),
) -> ApproveResponse:
    if not body.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval must be explicitly confirmed with approved=true",
        )
    try:
        return await service.approve_and_persist_draft(body.approval_token, actor_id)
    except (
        InvalidDraftStateError,
        ParentNotFoundError,
        ProvenanceStoreUnavailableError,
    ) as exc:
        raise _handle_domain_exception(exc)


@router.get("/{config_id}", response_model=PageConfigDetailResponse, status_code=status.HTTP_200_OK)
async def get_config(
    config_id: UUID,
    _: str = Depends(require_auth),
    service: PageConfigService = Depends(get_service),
) -> PageConfigDetailResponse:
    try:
        return await service.get_config(config_id)
    except ConfigNotFoundError as exc:
        raise _handle_domain_exception(exc)


@router.post("/{config_id}/draft", response_model=DiffResponse, status_code=status.HTTP_200_OK)
async def update_draft(
    config_id: UUID,
    body: GenerateUpdateDraftRequest,
    _: str = Depends(require_auth),
    service: PageConfigService = Depends(get_service),
) -> DiffResponse:
    try:
        return await service.generate_update_draft(config_id, body.product_id)
    except (
        ConfigNotFoundError,
        KnowledgeGraphUnavailableError,
    ) as exc:
        raise _handle_domain_exception(exc)


@router.post(
    "/{config_id}/delete-draft",
    response_model=DiffResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_draft(
    config_id: UUID,
    _: str = Depends(require_auth),
    service: PageConfigService = Depends(get_service),
) -> DiffResponse:
    try:
        return await service.generate_delete_draft(config_id)
    except ConfigNotFoundError as exc:
        raise _handle_domain_exception(exc)


@router.post(
    "/{config_id}/rollback",
    response_model=RollbackResponse,
    status_code=status.HTTP_200_OK,
)
async def rollback_config(
    config_id: UUID,
    body: RollbackRequest,
    actor_id: str = Depends(get_actor_id),
    _: str = Depends(require_auth),
    service: PageConfigService = Depends(get_service),
) -> RollbackResponse:
    try:
        return await service.rollback_to_version(config_id, body.to_version, actor_id)
    except (
        ConfigNotFoundError,
        ProvenanceStoreUnavailableError,
    ) as exc:
        raise _handle_domain_exception(exc)
