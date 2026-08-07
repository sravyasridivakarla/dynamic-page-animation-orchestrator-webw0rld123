"""Business logic for page config drafter."""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID, uuid4

import httpx

from .exceptions import (
    ConfigNotFoundError,
    InvalidDraftStateError,
    KnowledgeGraphUnavailableError,
    ParentNotFoundError,
    ProvenanceStoreUnavailableError,
)
from .models import (
    LayoutType,
    PageConfig,
    ScrollSection,
    SourcingTimelineEvent,
    VisibilityStatus,
    VisualRepresentation,
    VisualRepresentationType,
)
from .repository import PageConfigRepository
from .schema import (
    ApproveResponse,
    DiffChange,
    DiffOperation,
    DiffResponse,
    KGSource,
    PageConfigDetailResponse,
    PageConfigDraft,
    RollbackResponse,
    ScrollSectionDraft,
    ScrollSectionResponse,
    SourcingTimelineEventDraft,
    SourcingTimelineEventResponse,
    VisualRepresentationDraft,
    VisualRepresentationResponse,
    WorkflowState,
)

logger = logging.getLogger(__name__)

_draft_store: Dict[str, dict] = {}


class PageConfigService:
    def __init__(
        self,
        session,
        repository: PageConfigRepository,
        kg_client: httpx.AsyncClient,
        provenance_client: httpx.AsyncClient,
    ) -> None:
        self.session = session
        self.repository = repository
        self.kg_client = kg_client
        self.provenance_client = provenance_client

    async def generate_create_draft(self, product_id: str) -> DiffResponse:
        try:
            product_response = await self.kg_client.get(f"/products/{product_id}")
            product_response.raise_for_status()
            product_context = product_response.json()
        except Exception as exc:
            logger.warning("KG unavailable for create draft: %s", exc)
            raise KnowledgeGraphUnavailableError(
                "Knowledge Graph Service is unavailable"
            ) from exc

        try:
            et_response = await self.kg_client.get("/event-types")
            et_response.raise_for_status()
            valid_event_types = et_response.json().get("event_types", [])
        except Exception as exc:
            logger.warning("KG event-types unavailable: %s", exc)
            raise KnowledgeGraphUnavailableError(
                "Knowledge Graph Service is unavailable"
            ) from exc

        warnings = []

        page_title = product_context.get("page_title") or product_context.get("name", "")
        if not page_title:
            warnings.append("page_title is required but could not be derived from Knowledge Graph")

        meta_description = product_context.get("meta_description") or product_context.get(
            "description", ""
        )
        if not meta_description:
            warnings.append("meta_description is required but could not be derived from Knowledge Graph")

        layout_type = product_context.get("layout_type", "STANDARD")
        visibility_status = product_context.get("visibility_status", "DRAFT")

        scroll_sections = [
            ScrollSectionDraft(
                position=i,
                heading=s.get("heading", ""),
                content=s.get("content", ""),
                background_image_url=s.get("background_image_url", ""),
            )
            for i, s in enumerate(product_context.get("scroll_sections", []))
        ]

        visual_representations = [
            VisualRepresentationDraft(
                type=v.get("type", "IMAGE"),
                url=v.get("url", ""),
                alt_text=v.get("alt_text", ""),
                position=i,
            )
            for i, v in enumerate(product_context.get("visual_representations", []))
        ]

        sourcing_timeline_events = []
        for e in product_context.get("sourcing_timeline_events", []):
            event_type = e.get("event_type", "")
            if valid_event_types and event_type not in valid_event_types:
                warnings.append(
                    f"Event type '{event_type}' is not registered in Knowledge Graph; "
                    "merchandiser may override with explicit justification"
                )
            sourcing_timeline_events.append(
                SourcingTimelineEventDraft(
                    timestamp=datetime.now(timezone.utc),
                    event_type=event_type,
                    description=e.get("description", ""),
                )
            )

        draft = PageConfigDraft(
            product_id=product_id,
            page_title=page_title,
            meta_description=meta_description,
            layout_type=layout_type,
            visibility_status=visibility_status,
            scroll_sections=scroll_sections,
            visual_representations=visual_representations,
            sourcing_timeline_events=sourcing_timeline_events,
            workflow_state=WorkflowState.DRAFT_PENDING,
            validation_warnings=warnings,
        )

        approval_token = str(uuid4())
        _draft_store[approval_token] = {
            "draft": draft,
            "operation": DiffOperation.CREATE,
            "config_id": None,
        }

        kg_sources = [
            KGSource(
                field="page_title",
                source=f"KG:/products/{product_id}",
                contribution="Derived from product name",
            ),
            KGSource(
                field="layout_type",
                source=f"KG:/products/{product_id}",
                contribution="Derived from product category policy",
            ),
            KGSource(
                field="meta_description",
                source=f"KG:/products/{product_id}",
                contribution="Derived from product description",
            ),
        ]

        logger.info("Create draft generated for product_id=%s token=%s", product_id, approval_token)

        return DiffResponse(
            operation=DiffOperation.CREATE,
            draft=draft,
            prior_state=None,
            changes={},
            kg_sources=kg_sources,
            reasoning_trace=(
                f"Product {product_id} context retrieved from Knowledge Graph. "
                "Layout type derived from product category mapping. "
                "All child records populated from product catalog data."
            ),
            validation_warnings=warnings,
            approval_token=approval_token,
        )

    async def generate_update_draft(
        self, config_id: UUID, product_id: Optional[str] = None
    ) -> DiffResponse:
        current = await self.repository.get_by_id(config_id)
        effective_product_id = product_id or current.product_id

        try:
            product_response = await self.kg_client.get(f"/products/{effective_product_id}")
            product_response.raise_for_status()
            product_context = product_response.json()
        except Exception as exc:
            logger.warning("KG unavailable for update draft: %s", exc)
            raise KnowledgeGraphUnavailableError(
                "Knowledge Graph Service is unavailable"
            ) from exc

        try:
            et_response = await self.kg_client.get("/event-types")
            et_response.raise_for_status()
            valid_event_types = et_response.json().get("event_types", [])
        except Exception as exc:
            raise KnowledgeGraphUnavailableError(
                "Knowledge Graph Service is unavailable"
            ) from exc

        warnings = []
        changes: Dict[str, DiffChange] = {}

        new_page_title = (
            product_context.get("page_title")
            or product_context.get("name")
            or current.page_title
        )
        if new_page_title != current.page_title:
            changes["page_title"] = DiffChange(before=current.page_title, after=new_page_title)

        new_meta_description = (
            product_context.get("meta_description")
            or product_context.get("description")
            or current.meta_description
        )
        if new_meta_description != current.meta_description:
            changes["meta_description"] = DiffChange(
                before=current.meta_description, after=new_meta_description
            )

        new_layout_type = product_context.get("layout_type", current.layout_type.value)
        if new_layout_type != current.layout_type.value:
            changes["layout_type"] = DiffChange(
                before=current.layout_type.value, after=new_layout_type
            )

        new_visibility_status = product_context.get(
            "visibility_status", current.visibility_status.value
        )
        if new_visibility_status != current.visibility_status.value:
            changes["visibility_status"] = DiffChange(
                before=current.visibility_status.value, after=new_visibility_status
            )

        prior_state = PageConfigDraft(
            id=current.id,
            product_id=current.product_id,
            page_title=current.page_title,
            meta_description=current.meta_description,
            layout_type=current.layout_type.value,
            visibility_status=current.visibility_status.value,
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
                    type=v.type.value,
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
            validation_warnings=[],
        )

        new_sourcing_events = []
        for e in product_context.get("sourcing_timeline_events", []):
            event_type = e.get("event_type", "")
            if valid_event_types and event_type not in valid_event_types:
                warnings.append(
                    f"Event type '{event_type}' is not registered in Knowledge Graph"
                )
            new_sourcing_events.append(
                SourcingTimelineEventDraft(
                    timestamp=datetime.now(timezone.utc),
                    event_type=event_type,
                    description=e.get("description", ""),
                )
            )

        draft = PageConfigDraft(
            id=current.id,
            product_id=effective_product_id,
            page_title=new_page_title,
            meta_description=new_meta_description,
            layout_type=new_layout_type,
            visibility_status=new_visibility_status,
            scroll_sections=prior_state.scroll_sections,
            visual_representations=prior_state.visual_representations,
            sourcing_timeline_events=new_sourcing_events or prior_state.sourcing_timeline_events,
            workflow_state=WorkflowState.DRAFT_PENDING,
            validation_warnings=warnings,
        )

        approval_token = str(uuid4())
        _draft_store[approval_token] = {
            "draft": draft,
            "operation": DiffOperation.UPDATE,
            "config_id": str(config_id),
        }

        logger.info("Update draft generated for config_id=%s token=%s", config_id, approval_token)

        return DiffResponse(
            operation=DiffOperation.UPDATE,
            draft=draft,
            prior_state=prior_state,
            changes=changes,
            kg_sources=[
                KGSource(
                    field=field,
                    source=f"KG:/products/{effective_product_id}",
                    contribution="Updated from Knowledge Graph product context",
                )
                for field in changes
            ],
            reasoning_trace=(
                f"Existing config {config_id} compared against Knowledge Graph data for "
                f"product {effective_product_id}. {len(changes)} field(s) differ from current state."
            ),
            validation_warnings=warnings,
            approval_token=approval_token,
        )

    async def generate_delete_draft(self, config_id: UUID) -> DiffResponse:
        current = await self.repository.get_by_id(config_id)

        draft = PageConfigDraft(
            id=current.id,
            product_id=current.product_id,
            page_title=current.page_title,
            meta_description=current.meta_description,
            layout_type=current.layout_type.value,
            visibility_status=current.visibility_status.value,
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
                    type=v.type.value,
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
            workflow_state=WorkflowState.DRAFT_PENDING,
            validation_warnings=[],
        )

        changes = {
            "page_title": DiffChange(before=current.page_title, after=None),
            "meta_description": DiffChange(before=current.meta_description, after=None),
            "layout_type": DiffChange(before=current.layout_type.value, after=None),
            "visibility_status": DiffChange(before=current.visibility_status.value, after=None),
        }

        approval_token = str(uuid4())
        _draft_store[approval_token] = {
            "draft": draft,
            "operation": DiffOperation.DELETE,
            "config_id": str(config_id),
        }

        logger.info("Delete draft generated for config_id=%s token=%s", config_id, approval_token)

        return DiffResponse(
            operation=DiffOperation.DELETE,
            draft=draft,
            prior_state=None,
            changes=changes,
            kg_sources=[],
            reasoning_trace=(
                f"Proposed deletion of page config {config_id} including "
                f"{len(current.scroll_sections)} scroll section(s), "
                f"{len(current.visual_representations)} visual representation(s), "
                f"and {len(current.sourcing_timeline_events)} sourcing timeline event(s). "
                "Deletion is irreversible; manual intervention required to restore downstream effects."
            ),
            validation_warnings=[],
            approval_token=approval_token,
        )

    async def approve_and_persist_draft(
        self, approval_token: str, approver_id: str
    ) -> ApproveResponse:
        entry = _draft_store.get(approval_token)
        if not entry:
            raise InvalidDraftStateError("Draft not found or approval token is invalid")

        draft: PageConfigDraft = entry["draft"]
        operation: DiffOperation = entry["operation"]
        config_id_str: Optional[str] = entry.get("config_id")

        if draft.workflow_state != WorkflowState.DRAFT_PENDING:
            raise InvalidDraftStateError(
                f"Draft is in state '{draft.workflow_state}', expected DRAFT_PENDING"
            )

        result_id: UUID

        try:
            if operation == DiffOperation.CREATE:
                config = PageConfig(
                    product_id=draft.product_id,
                    page_title=draft.page_title,
                    meta_description=draft.meta_description,
                    layout_type=LayoutType(draft.layout_type),
                    visibility_status=VisibilityStatus(draft.visibility_status),
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
                visual_representations = [
                    VisualRepresentation(
                        type=VisualRepresentationType(v.type),
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
                persisted = await self.repository.create(
                    config, scroll_sections, visual_representations, events
                )
                result_id = persisted.id

            elif operation == DiffOperation.UPDATE:
                if not config_id_str:
                    raise ParentNotFoundError("No config_id associated with this draft")
                config_id = UUID(config_id_str)
                try:
                    await self.repository.get_by_id(config_id)
                except ConfigNotFoundError:
                    raise ParentNotFoundError(f"Parent config {config_id} not found")
                updates = {
                    "page_title": draft.page_title,
                    "meta_description": draft.meta_description,
                    "layout_type": LayoutType(draft.layout_type),
                    "visibility_status": VisibilityStatus(draft.visibility_status),
                    "updated_by": approver_id,
                }
                persisted = await self.repository.update(config_id, updates)
                result_id = persisted.id

            elif operation == DiffOperation.DELETE:
                if not config_id_str:
                    raise ParentNotFoundError("No config_id associated with this draft")
                config_id = UUID(config_id_str)
                try:
                    await self.repository.get_by_id(config_id)
                except ConfigNotFoundError:
                    raise ParentNotFoundError(f"Parent config {config_id} not found")
                await self.repository.delete(config_id)
                result_id = config_id

            else:
                raise InvalidDraftStateError(f"Unknown operation: {operation}")

        except (InvalidDraftStateError, ParentNotFoundError):
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            raise

        try:
            prov_response = await self.provenance_client.post(
                "/audit",
                json={
                    "action": f"{operation.value}_APPROVED",
                    "actor_id": approver_id,
                    "config_id": str(result_id),
                    "approval_token": approval_token,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "draft_summary": {
                        "product_id": draft.product_id,
                        "page_title": draft.page_title,
                        "validation_warnings": draft.validation_warnings,
                    },
                },
            )
            prov_response.raise_for_status()
        except Exception as exc:
            await self.session.rollback()
            logger.error("Provenance Store unavailable: %s", exc)
            raise ProvenanceStoreUnavailableError(
                "Provenance Store is unavailable; draft not persisted"
            ) from exc

        await self.session.commit()
        draft.workflow_state = WorkflowState.PERSISTED

        logger.info(
            "Draft approved and persisted: operation=%s config_id=%s actor=%s",
            operation.value,
            result_id,
            approver_id,
        )

        return ApproveResponse(id=result_id, status="PERSISTED")

    async def rollback_to_version(
        self, config_id: UUID, to_version: UUID, actor_id: str
    ) -> RollbackResponse:
        try:
            version_response = await self.provenance_client.get(f"/versions/{to_version}")
            version_response.raise_for_status()
            prior_data = version_response.json()
        except Exception as exc:
            logger.error("Provenance Store unavailable for rollback: %s", exc)
            raise ProvenanceStoreUnavailableError(
                "Provenance Store is unavailable"
            ) from exc

        try:
            await self.repository.get_by_id(config_id)
            await self.repository.delete(config_id)
        except ConfigNotFoundError:
            pass

        config_data = prior_data.get("config", {})
        restored_config = PageConfig(
            product_id=config_data.get("product_id", ""),
            page_title=config_data.get("page_title", ""),
            meta_description=config_data.get("meta_description", ""),
            layout_type=LayoutType(config_data.get("layout_type", "STANDARD")),
            visibility_status=VisibilityStatus(config_data.get("visibility_status", "DRAFT")),
            created_by=config_data.get("created_by", actor_id),
            updated_by=actor_id,
        )
        scroll_sections = [
            ScrollSection(
                position=s.get("position", 0),
                heading=s.get("heading", ""),
                content=s.get("content", ""),
                background_image_url=s.get("background_image_url", ""),
            )
            for s in prior_data.get("scroll_sections", [])
        ]
        visual_representations = [
            VisualRepresentation(
                type=VisualRepresentationType(v.get("type", "IMAGE")),
                url=v.get("url", ""),
                alt_text=v.get("alt_text", ""),
                position=v.get("position", 0),
            )
            for v in prior_data.get("visual_representations", [])
        ]
        events = [
            SourcingTimelineEvent(
                timestamp=datetime.fromisoformat(e["timestamp"]),
                event_type=e.get("event_type", ""),
                description=e.get("description", ""),
            )
            for e in prior_data.get("sourcing_timeline_events", [])
        ]

        restored = await self.repository.create(
            restored_config, scroll_sections, visual_representations, events
        )

        try:
            prov_response = await self.provenance_client.post(
                "/audit",
                json={
                    "action": "ROLLBACK",
                    "actor_id": actor_id,
                    "config_id": str(restored.id),
                    "rolled_back_from": str(config_id),
                    "rolled_back_to_version": str(to_version),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            prov_response.raise_for_status()
        except Exception as exc:
            await self.session.rollback()
            raise ProvenanceStoreUnavailableError(
                "Provenance Store is unavailable; rollback not completed"
            ) from exc

        await self.session.commit()

        logger.info(
            "Rollback completed: config_id=%s to_version=%s actor=%s",
            restored.id,
            to_version,
            actor_id,
        )

        return RollbackResponse(id=restored.id, status="RESTORED")

    async def get_config(self, config_id: UUID) -> PageConfigDetailResponse:
        config = await self.repository.get_by_id(config_id)

        return PageConfigDetailResponse(
            id=config.id,
            product_id=config.product_id,
            page_title=config.page_title,
            meta_description=config.meta_description,
            layout_type=config.layout_type.value,
            visibility_status=config.visibility_status.value,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
            updated_by=config.updated_by,
            scroll_sections=[
                ScrollSectionResponse(
                    id=s.id,
                    config_id=s.config_id,
                    position=s.position,
                    heading=s.heading,
                    content=s.content,
                    background_image_url=s.background_image_url,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in config.scroll_sections
            ],
            visual_representations=[
                VisualRepresentationResponse(
                    id=v.id,
                    config_id=v.config_id,
                    type=v.type.value,
                    url=v.url,
                    alt_text=v.alt_text,
                    position=v.position,
                    created_at=v.created_at,
                    updated_at=v.updated_at,
                )
                for v in config.visual_representations
            ],
            sourcing_timeline_events=[
                SourcingTimelineEventResponse(
                    id=e.id,
                    config_id=e.config_id,
                    timestamp=e.timestamp,
                    event_type=e.event_type,
                    description=e.description,
                    created_at=e.created_at,
                    updated_at=e.updated_at,
                )
                for e in config.sourcing_timeline_events
            ],
        )
