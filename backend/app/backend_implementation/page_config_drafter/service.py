"""Business logic for page config drafter."""

import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import (
    ConfigNotFoundError,
    InvalidDraftStateError,
    KnowledgeGraphUnavailableError,
    ParentNotFoundError,
    ProvenanceStoreUnavailableError,
)
from .models import PageConfig, ScrollSection, SourcingTimelineEvent, VisualRepresentation
from .repository import PageConfigRepository
from .schema import (
    DiffChange,
    DiffResponse,
    DraftOperation,
    KGSource,
    PageConfigDraft,
    ScrollSectionDraft,
    SourcingTimelineEventDraft,
    VisualRepresentationDraft,
    WorkflowState,
)

logger = logging.getLogger(__name__)

_draft_store: dict[str, tuple[DraftOperation, PageConfigDraft]] = {}


class PageConfigService:
    def __init__(
        self,
        repo: PageConfigRepository,
        kg_client: httpx.AsyncClient,
        provenance_client: httpx.AsyncClient,
        db: AsyncSession,
    ):
        self.repo = repo
        self.kg_client = kg_client
        self.provenance_client = provenance_client
        self.db = db

    async def generate_create_draft(self, product_id: str) -> DiffResponse:
        logger.info("Generating create draft", extra={"product_id": product_id})

        try:
            kg_resp = await self.kg_client.get(f"/products/{product_id}/context")
            kg_resp.raise_for_status()
            product_ctx = kg_resp.json()
        except httpx.HTTPStatusError as exc:
            raise KnowledgeGraphUnavailableError(
                f"KG returned {exc.response.status_code}"
            )
        except httpx.RequestError as exc:
            raise KnowledgeGraphUnavailableError(str(exc))

        valid_event_types: set[str] = set()
        try:
            et_resp = await self.kg_client.get("/event-types")
            et_resp.raise_for_status()
            valid_event_types = {
                et["type"] for et in et_resp.json().get("event_types", [])
            }
        except Exception:
            pass

        validation_warnings: list[str] = []
        for field in ("page_title", "meta_description", "layout_type", "visibility_status"):
            if not product_ctx.get(field):
                validation_warnings.append(
                    f"{field} is required but missing from Knowledge Graph context"
                )

        scroll_sections = [
            ScrollSectionDraft(**s) for s in product_ctx.get("scroll_sections", [])
        ]
        visual_representations = [
            VisualRepresentationDraft(**v)
            for v in product_ctx.get("visual_representations", [])
        ]
        sourcing_events: list[SourcingTimelineEventDraft] = []
        for e in product_ctx.get("sourcing_timeline_events", []):
            if valid_event_types and e.get("event_type") not in valid_event_types:
                validation_warnings.append(
                    f"Event type '{e.get('event_type')}' is not registered in the Knowledge Graph"
                )
            sourcing_events.append(SourcingTimelineEventDraft(**e))

        draft = PageConfigDraft(
            product_id=product_id,
            page_title=product_ctx.get("page_title", ""),
            meta_description=product_ctx.get("meta_description", ""),
            layout_type=product_ctx.get("layout_type", "STANDARD"),
            visibility_status=product_ctx.get("visibility_status", "DRAFT"),
            scroll_sections=scroll_sections,
            visual_representations=visual_representations,
            sourcing_timeline_events=sourcing_events,
            workflow_state=WorkflowState.DRAFT_PENDING,
            validation_warnings=validation_warnings,
        )

        approval_token = str(uuid.uuid4())
        _draft_store[approval_token] = (DraftOperation.CREATE, draft)

        kg_sources = [
            KGSource(
                field=field,
                source=f"/products/{product_id}/context",
                contribution="Populated from Knowledge Graph product context",
            )
            for field in ("page_title", "meta_description", "layout_type", "visibility_status")
        ]

        return DiffResponse(
            operation=DraftOperation.CREATE,
            draft=draft,
            prior_state=None,
            changes={
                field: DiffChange(before=None, after=str(getattr(draft, field, "")))
                for field in ("page_title", "meta_description", "layout_type", "visibility_status")
            },
            kg_sources=kg_sources,
            reasoning_trace=(
                f"Product {product_id} context retrieved from Knowledge Graph; "
                "layout and visibility defaulted from product category policy."
            ),
            validation_warnings=validation_warnings,
            approval_token=approval_token,
        )

    async def generate_update_draft(
        self, config_id: uuid.UUID, product_id: str
    ) -> DiffResponse:
        logger.info("Generating update draft", extra={"config_id": str(config_id)})

        current = await self.repo.get_by_id(config_id)

        try:
            kg_resp = await self.kg_client.get(f"/products/{product_id}/context")
            kg_resp.raise_for_status()
            product_ctx = kg_resp.json()
        except httpx.HTTPStatusError as exc:
            raise KnowledgeGraphUnavailableError(
                f"KG returned {exc.response.status_code}"
            )
        except httpx.RequestError as exc:
            raise KnowledgeGraphUnavailableError(str(exc))

        new_values = {
            "page_title": product_ctx.get("page_title", current.page_title),
            "meta_description": product_ctx.get("meta_description", current.meta_description),
            "layout_type": product_ctx.get("layout_type", current.layout_type),
            "visibility_status": product_ctx.get("visibility_status", current.visibility_status),
        }
        current_values = {
            "page_title": current.page_title,
            "meta_description": current.meta_description,
            "layout_type": current.layout_type,
            "visibility_status": current.visibility_status,
        }

        changes: dict[str, DiffChange] = {
            field: DiffChange(before=current_values[field], after=new_values[field])
            for field in new_values
            if new_values[field] != current_values[field]
        }

        prior_state = PageConfigDraft(
            id=current.id,
            product_id=current.product_id,
            page_title=current.page_title,
            meta_description=current.meta_description,
            layout_type=current.layout_type,
            visibility_status=current.visibility_status,
            scroll_sections=[
                ScrollSectionDraft(
                    id=s.id,
                    position=s.position,
                    heading=s.heading,
                    content=s.content,
                    background_image_url=s.background_image_url,
                )
                for s in current.scroll_sections
            ],
            visual_representations=[
                VisualRepresentationDraft(
                    id=v.id,
                    type=v.type,
                    url=v.url,
                    alt_text=v.alt_text,
                    position=v.position,
                )
                for v in current.visual_representations
            ],
            sourcing_timeline_events=[
                SourcingTimelineEventDraft(
                    id=e.id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    description=e.description,
                )
                for e in current.sourcing_timeline_events
            ],
            workflow_state=WorkflowState.PERSISTED,
        )

        validation_warnings: list[str] = []
        for field in ("page_title", "meta_description", "layout_type", "visibility_status"):
            if not product_ctx.get(field):
                validation_warnings.append(
                    f"{field} is required but missing from Knowledge Graph context"
                )

        draft = PageConfigDraft(
            id=current.id,
            product_id=product_id,
            page_title=new_values["page_title"],
            meta_description=new_values["meta_description"],
            layout_type=new_values["layout_type"],
            visibility_status=new_values["visibility_status"],
            scroll_sections=prior_state.scroll_sections,
            visual_representations=prior_state.visual_representations,
            sourcing_timeline_events=prior_state.sourcing_timeline_events,
            workflow_state=WorkflowState.DRAFT_PENDING,
            validation_warnings=validation_warnings,
        )

        approval_token = str(uuid.uuid4())
        _draft_store[approval_token] = (DraftOperation.UPDATE, draft)

        return DiffResponse(
            operation=DraftOperation.UPDATE,
            draft=draft,
            prior_state=prior_state,
            changes=changes,
            kg_sources=[
                KGSource(
                    field=field,
                    source=f"/products/{product_id}/context",
                    contribution="Updated from Knowledge Graph product context",
                )
                for field in changes
            ],
            reasoning_trace=(
                f"Config {config_id} fields compared against Knowledge Graph "
                f"context for product {product_id}."
            ),
            validation_warnings=validation_warnings,
            approval_token=approval_token,
        )

    async def generate_delete_draft(self, config_id: uuid.UUID) -> DiffResponse:
        logger.info("Generating delete draft", extra={"config_id": str(config_id)})

        current = await self.repo.get_by_id(config_id)

        child_summary = (
            f"PageConfig {current.id} with {len(current.scroll_sections)} scroll sections, "
            f"{len(current.visual_representations)} visual representations, "
            f"{len(current.sourcing_timeline_events)} sourcing timeline events"
        )

        prior_state = PageConfigDraft(
            id=current.id,
            product_id=current.product_id,
            page_title=current.page_title,
            meta_description=current.meta_description,
            layout_type=current.layout_type,
            visibility_status=current.visibility_status,
            scroll_sections=[
                ScrollSectionDraft(
                    id=s.id,
                    position=s.position,
                    heading=s.heading,
                    content=s.content,
                    background_image_url=s.background_image_url,
                )
                for s in current.scroll_sections
            ],
            visual_representations=[
                VisualRepresentationDraft(
                    id=v.id,
                    type=v.type,
                    url=v.url,
                    alt_text=v.alt_text,
                    position=v.position,
                )
                for v in current.visual_representations
            ],
            sourcing_timeline_events=[
                SourcingTimelineEventDraft(
                    id=e.id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    description=e.description,
                )
                for e in current.sourcing_timeline_events
            ],
            workflow_state=WorkflowState.PERSISTED,
        )

        draft = PageConfigDraft(
            id=current.id,
            product_id=current.product_id,
            page_title=current.page_title,
            meta_description=current.meta_description,
            layout_type=current.layout_type,
            visibility_status=current.visibility_status,
            scroll_sections=prior_state.scroll_sections,
            visual_representations=prior_state.visual_representations,
            sourcing_timeline_events=prior_state.sourcing_timeline_events,
            workflow_state=WorkflowState.DRAFT_PENDING,
        )

        approval_token = str(uuid.uuid4())
        _draft_store[approval_token] = (DraftOperation.DELETE, draft)

        return DiffResponse(
            operation=DraftOperation.DELETE,
            draft=draft,
            prior_state=prior_state,
            changes={"record": DiffChange(before=child_summary, after=None)},
            kg_sources=[],
            reasoning_trace=(
                f"Deletion of config {config_id} including all child records proposed for review."
            ),
            validation_warnings=[],
            approval_token=approval_token,
        )

    async def approve_and_persist_draft(
        self, approval_token: str, approved: bool, approver_id: str
    ) -> tuple[uuid.UUID, str]:
        logger.info(
            "Approving draft",
            extra={"approval_token": approval_token, "approved": approved},
        )

        entry = _draft_store.get(approval_token)
        if entry is None:
            raise InvalidDraftStateError("Approval token not found or already used")

        operation, draft = entry

        if draft.workflow_state != WorkflowState.DRAFT_PENDING:
            raise InvalidDraftStateError(
                f"Draft is in state {draft.workflow_state}, expected DRAFT_PENDING"
            )

        if not approved:
            del _draft_store[approval_token]
            raise InvalidDraftStateError("Draft was rejected by approver")

        try:
            prov_resp = await self.provenance_client.post(
                "/actions",
                json={
                    "action": "approve_draft",
                    "actor_id": approver_id,
                    "approval_token": approval_token,
                    "operation": operation.value,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "draft": draft.model_dump(mode="json"),
                },
            )
            prov_resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProvenanceStoreUnavailableError(
                f"Provenance Store returned {exc.response.status_code}"
            )
        except httpx.RequestError as exc:
            raise ProvenanceStoreUnavailableError(str(exc))

        config_id: uuid.UUID
        status: str

        if operation == DraftOperation.CREATE:
            config = PageConfig(
                product_id=draft.product_id,
                page_title=draft.page_title,
                meta_description=draft.meta_description,
                layout_type=draft.layout_type,
                visibility_status=draft.visibility_status,
                created_by=approver_id,
                updated_by=approver_id,
            )
            scroll_sections = [
                ScrollSection(
                    position=s.position,
                    heading=s.heading,
                    content=s.content,
                    background_image_url=s.background_image_url,
                )
                for s in draft.scroll_sections
            ]
            visual_reps = [
                VisualRepresentation(
                    type=v.type,
                    url=v.url,
                    alt_text=v.alt_text,
                    position=v.position,
                )
                for v in draft.visual_representations
            ]
            events = [
                SourcingTimelineEvent(
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    description=e.description,
                )
                for e in draft.sourcing_timeline_events
            ]
            persisted = await self.repo.create(config, scroll_sections, visual_reps, events)
            await self.db.commit()
            config_id = persisted.id
            status = "PERSISTED"

        elif operation == DraftOperation.UPDATE:
            assert draft.id is not None
            updates = {
                "page_title": draft.page_title,
                "meta_description": draft.meta_description,
                "layout_type": draft.layout_type,
                "visibility_status": draft.visibility_status,
                "updated_by": approver_id,
            }
            try:
                persisted = await self.repo.update(draft.id, updates)
            except ConfigNotFoundError:
                raise ParentNotFoundError(
                    f"Config {draft.id} no longer exists; cannot complete update"
                )
            await self.db.commit()
            config_id = persisted.id
            status = "PERSISTED"

        else:
            assert draft.id is not None
            try:
                await self.repo.delete(draft.id)
            except ConfigNotFoundError:
                raise ParentNotFoundError(
                    f"Config {draft.id} no longer exists; cannot complete deletion"
                )
            await self.db.commit()
            config_id = draft.id
            status = "DELETED"

        del _draft_store[approval_token]
        logger.info("Draft persisted", extra={"config_id": str(config_id), "status": status})
        return config_id, status

    async def rollback_to_version(
        self, config_id: uuid.UUID, to_version: uuid.UUID, actor_id: str
    ) -> tuple[uuid.UUID, str]:
        logger.info(
            "Rolling back config",
            extra={"config_id": str(config_id), "to_version": str(to_version)},
        )

        try:
            prov_resp = await self.provenance_client.get(f"/versions/{to_version}")
            prov_resp.raise_for_status()
            version_data = prov_resp.json()
        except httpx.HTTPStatusError as exc:
            raise ProvenanceStoreUnavailableError(
                f"Provenance Store returned {exc.response.status_code}"
            )
        except httpx.RequestError as exc:
            raise ProvenanceStoreUnavailableError(str(exc))

        prior = version_data.get("draft", {})
        updates = {
            "page_title": prior.get("page_title"),
            "meta_description": prior.get("meta_description"),
            "layout_type": prior.get("layout_type"),
            "visibility_status": prior.get("visibility_status"),
            "updated_by": actor_id,
        }
        try:
            restored = await self.repo.update(config_id, updates)
        except ConfigNotFoundError:
            raise ParentNotFoundError(
                f"Config {config_id} does not exist; cannot roll back"
            )

        try:
            await self.provenance_client.post(
                "/actions",
                json={
                    "action": "rollback",
                    "actor_id": actor_id,
                    "config_id": str(config_id),
                    "to_version": str(to_version),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:
            pass

        await self.db.commit()
        logger.info("Rollback complete", extra={"config_id": str(config_id)})
        return restored.id, "RESTORED"
