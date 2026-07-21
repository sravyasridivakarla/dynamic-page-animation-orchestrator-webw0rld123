"""Business logic for Page Config Drafter."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.kg_client import KGServiceUnavailableError, KnowledgeGraphClient
from app.clients.provenance_client import ProvenanceStoreClient, ProvenanceStoreUnavailableError

from .models import (
    PageConfig,
    ProvenanceRecord,
    ScrollSection,
    SourcingTimelineEvent,
    VisualRepresentation,
    WorkflowState,
)
from .repository import PageConfigRepository, ProvenanceRecordRepository
from .schema import (
    ApproveRequest,
    CompletenessWarning,
    DeleteConfirmResponse,
    DeleteProposalResponse,
    DiffResponse,
    DraftRequest,
    EventTypeWarning,
    RejectRequest,
    RollbackResponse,
)

logger = structlog.get_logger()


class KGUnavailableFallbackError(Exception):
    pass


class ProvenanceUnavailableError(Exception):
    pass


class InvalidStateError(Exception):
    pass


class NotFoundError(Exception):
    pass


class PageConfigDrafterService:
    def __init__(
        self,
        session: AsyncSession,
        kg_client: KnowledgeGraphClient,
        provenance_client: ProvenanceStoreClient,
    ):
        self._session = session
        self._kg = kg_client
        self._provenance = provenance_client
        self._repo = PageConfigRepository(session)
        self._prov_repo = ProvenanceRecordRepository(session)

    # --- draft generation ---

    async def generate_draft(self, request: DraftRequest) -> PageConfig:
        # FR-DG1: KG call; raise fallback error if unavailable
        try:
            kg_context = await self._kg.get_product_context(request.product_id)
        except KGServiceUnavailableError as exc:
            raise KGUnavailableFallbackError(
                "Knowledge Graph Service unavailable. Use the legacy manual create-config form."
            ) from exc

        # FR-DG5: validate event types against KG
        event_type_warnings: List[EventTypeWarning] = []
        if request.sourcing_timeline_events:
            types = [e.event_type for e in request.sourcing_timeline_events]
            try:
                validation_result = await self._kg.validate_event_types(types)
                for et, valid in validation_result.items():
                    if not valid:
                        event_type_warnings.append(
                            EventTypeWarning(
                                event_type=et,
                                message=f"Event type '{et}' is not recognized by the Knowledge Graph.",
                            )
                        )
            except KGServiceUnavailableError:
                for et in types:
                    event_type_warnings.append(
                        EventTypeWarning(
                            event_type=et,
                            message=f"Could not validate event type '{et}'; KG unavailable.",
                        )
                    )

        # FR-DG3: create parent first, flush to get ID
        page_config = PageConfig(
            product_id=request.product_id,
            workflow_state=WorkflowState.draft,
            version=1,
        )
        page_config = await self._repo.create(page_config)

        # FR-DG2: create all children with valid parent ID
        for sec in request.scroll_sections:
            await self._repo.add_scroll_section(
                ScrollSection(
                    page_config_id=page_config.id,
                    order=sec.order,
                    content=sec.content,
                )
            )

        for vr in request.visual_representations:
            await self._repo.add_visual_representation(
                VisualRepresentation(
                    page_config_id=page_config.id,
                    type=vr.type,
                    url=vr.url,
                )
            )

        invalid_event_types = {w.event_type for w in event_type_warnings}
        for ev in request.sourcing_timeline_events:
            validated = ev.event_type not in invalid_event_types
            await self._repo.add_sourcing_event(
                SourcingTimelineEvent(
                    page_config_id=page_config.id,
                    event_type=ev.event_type,
                    date=ev.date,
                    validated=validated,
                )
            )

        diff = self._build_diff_dict(page_config, event_type_warnings=event_type_warnings)

        # FR-AU1 & FR-AU2: write provenance before commit
        await self._write_provenance(
            page_config_id=page_config.id,
            action_type="generate_draft",
            inputs=request.model_dump(mode="json"),
            sources={"kg_context": kg_context},
            reasoning_trace="Draft generated from Knowledge Graph context.",
            diff_presented=diff,
        )

        await self._session.commit()
        await self._session.refresh(page_config)
        return page_config

    # --- diff retrieval ---

    async def get_draft_diff(self, draft_id: UUID) -> DiffResponse:
        page_config = await self._get_or_404(draft_id)
        completeness_warnings = self._check_completeness(page_config)
        prov_records = await self._prov_repo.get_by_config_ordered(draft_id)
        event_type_warnings: List[EventTypeWarning] = []
        if prov_records:
            last = prov_records[0]
            for ev_warn in last.diff_presented.get("event_type_warnings", []):
                event_type_warnings.append(EventTypeWarning(**ev_warn))

        return self._build_diff_response(
            page_config,
            completeness_warnings=completeness_warnings,
            event_type_warnings=event_type_warnings,
        )

    # --- approval ---

    async def process_approval(self, draft_id: UUID, request: ApproveRequest) -> PageConfig:
        page_config = await self._get_or_404(draft_id)
        if page_config.workflow_state != WorkflowState.draft:
            raise InvalidStateError(f"Config {draft_id} is not in draft state.")

        diff = self._build_diff_dict(page_config)
        await self._write_provenance(
            page_config_id=page_config.id,
            action_type="approve",
            inputs=request.model_dump(mode="json"),
            sources={},
            reasoning_trace="Merchandiser approved the draft.",
            diff_presented=diff,
            human_decision="approved",
            justification=request.justification,
        )

        page_config.workflow_state = WorkflowState.approved
        page_config.version += 1
        await self._repo.update(page_config)
        await self._session.commit()
        await self._session.refresh(page_config)
        return page_config

    # --- rejection ---

    async def process_rejection(self, draft_id: UUID, request: RejectRequest) -> PageConfig:
        page_config = await self._get_or_404(draft_id)
        if page_config.workflow_state != WorkflowState.draft:
            raise InvalidStateError(f"Config {draft_id} is not in draft state.")

        diff = self._build_diff_dict(page_config)
        await self._write_provenance(
            page_config_id=page_config.id,
            action_type="reject",
            inputs=request.model_dump(mode="json"),
            sources={},
            reasoning_trace="Merchandiser rejected the draft.",
            diff_presented=diff,
            human_decision="rejected",
            justification=request.justification,
        )

        page_config.workflow_state = WorkflowState.rejected
        await self._repo.update(page_config)
        await self._session.commit()
        await self._session.refresh(page_config)
        return page_config

    # --- rollback ---

    async def rollback_config(self, config_id: UUID) -> RollbackResponse:
        page_config = await self._get_or_404(config_id)
        prov_records = await self._prov_repo.get_by_config_ordered(config_id)
        if len(prov_records) < 2:
            raise InvalidStateError("No prior version available for rollback.")

        prior_prov = prov_records[1]
        prior_diff = prior_prov.diff_presented
        prior_version = prior_diff.get("version", page_config.version - 1)

        diff = self._build_diff_dict(page_config)
        await self._write_provenance(
            page_config_id=page_config.id,
            action_type="rollback",
            inputs={"target_provenance_id": str(prior_prov.id)},
            sources={"prior_diff": prior_diff},
            reasoning_trace=f"Rolling back to version {prior_version}.",
            diff_presented=diff,
        )

        page_config.workflow_state = WorkflowState.draft
        page_config.version = prior_version
        await self._repo.update(page_config)
        await self._session.commit()

        return RollbackResponse(
            config_id=config_id,
            restored_version=prior_version,
            message=f"Rolled back to version {prior_version}.",
        )

    # --- deletion ---

    async def propose_deletion(self, config_id: UUID) -> DeleteProposalResponse:
        page_config = await self._get_or_404(config_id)
        diff_response = self._build_diff_response(page_config, unwind_option=True)
        diff_dict = self._build_diff_dict(page_config, unwind_option=True)

        await self._write_provenance(
            page_config_id=page_config.id,
            action_type="propose_deletion",
            inputs={"config_id": str(config_id)},
            sources={},
            reasoning_trace="Deletion proposed; awaiting human confirmation.",
            diff_presented=diff_dict,
        )

        page_config.workflow_state = WorkflowState.pending_deletion
        await self._repo.update(page_config)
        await self._session.commit()

        return DeleteProposalResponse(
            config_id=config_id,
            workflow_state=WorkflowState.pending_deletion,
            diff=diff_response,
            unwind_option=True,
            message="Deletion proposed. Please confirm to proceed. Downstream effects must be unwound manually.",
        )

    async def execute_confirmed_deletion(self, config_id: UUID) -> DeleteConfirmResponse:
        page_config = await self._get_or_404(config_id)
        if page_config.workflow_state != WorkflowState.pending_deletion:
            raise InvalidStateError(
                f"Config {config_id} is not in pending_deletion state. Propose deletion first."
            )

        diff = self._build_diff_dict(page_config)
        await self._write_provenance(
            page_config_id=page_config.id,
            action_type="delete_confirmed",
            inputs={"config_id": str(config_id)},
            sources={},
            reasoning_trace="Merchandiser confirmed deletion. No automated compensation will follow.",
            diff_presented=diff,
            human_decision="confirmed_deletion",
        )

        await self._repo.delete(page_config)
        await self._session.commit()

        return DeleteConfirmResponse(
            config_id=config_id,
            message="Config deleted. Downstream effects must be unwound manually.",
        )

    # --- internal helpers ---

    async def _get_or_404(self, config_id: UUID) -> PageConfig:
        page_config = await self._repo.get_by_id(config_id)
        if page_config is None:
            raise NotFoundError(f"PageConfig {config_id} not found.")
        return page_config

    async def _write_provenance(
        self,
        page_config_id: UUID,
        action_type: str,
        inputs: Dict[str, Any],
        sources: Dict[str, Any],
        reasoning_trace: str,
        diff_presented: Dict[str, Any],
        human_decision: Optional[str] = None,
        justification: Optional[str] = None,
    ) -> None:
        payload = {
            "page_config_id": str(page_config_id),
            "action_type": action_type,
            "inputs": inputs,
            "sources": sources,
            "reasoning_trace": reasoning_trace,
            "diff_presented": diff_presented,
            "human_decision": human_decision,
            "justification": justification,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self._provenance.record_action(payload)
        except ProvenanceStoreUnavailableError as exc:
            raise ProvenanceUnavailableError(
                "Provenance Store unavailable. Action blocked until store is reachable."
            ) from exc

        record = ProvenanceRecord(
            page_config_id=page_config_id,
            action_type=action_type,
            inputs=inputs,
            sources=sources,
            reasoning_trace=reasoning_trace,
            diff_presented=diff_presented,
            human_decision=human_decision,
            justification=justification,
        )
        await self._prov_repo.append(record)

    def _check_completeness(self, page_config: PageConfig) -> List[CompletenessWarning]:
        warnings: List[CompletenessWarning] = []
        if not page_config.scroll_sections:
            warnings.append(
                CompletenessWarning(field="scroll_sections", message="No scroll sections defined.")
            )
        if not page_config.visual_representations:
            warnings.append(
                CompletenessWarning(
                    field="visual_representations", message="No visual representations defined."
                )
            )
        if not page_config.sourcing_timeline_events:
            warnings.append(
                CompletenessWarning(
                    field="sourcing_timeline_events",
                    message="No sourcing timeline events defined.",
                )
            )
        return warnings

    def _build_diff_dict(
        self,
        page_config: PageConfig,
        event_type_warnings: Optional[List[EventTypeWarning]] = None,
        unwind_option: bool = False,
    ) -> Dict[str, Any]:
        return {
            "draft_id": str(page_config.id),
            "product_id": page_config.product_id,
            "workflow_state": page_config.workflow_state.value,
            "version": page_config.version,
            "scroll_sections": [
                {"id": str(s.id), "order": s.order, "content": s.content}
                for s in (page_config.scroll_sections or [])
            ],
            "visual_representations": [
                {"id": str(v.id), "type": v.type, "url": v.url}
                for v in (page_config.visual_representations or [])
            ],
            "sourcing_timeline_events": [
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "validated": e.validated,
                }
                for e in (page_config.sourcing_timeline_events or [])
            ],
            "event_type_warnings": (
                [w.model_dump() for w in event_type_warnings] if event_type_warnings else []
            ),
            "unwind_option": unwind_option,
        }

    def _build_diff_response(
        self,
        page_config: PageConfig,
        completeness_warnings: Optional[List[CompletenessWarning]] = None,
        event_type_warnings: Optional[List[EventTypeWarning]] = None,
        unwind_option: bool = False,
    ) -> DiffResponse:
        from .schema import (
            ScrollSectionResponse,
            SourcingTimelineEventResponse,
            VisualRepresentationResponse,
        )

        return DiffResponse(
            draft_id=page_config.id,
            product_id=page_config.product_id,
            workflow_state=page_config.workflow_state,
            scroll_sections=[
                ScrollSectionResponse.model_validate(s)
                for s in (page_config.scroll_sections or [])
            ],
            visual_representations=[
                VisualRepresentationResponse.model_validate(v)
                for v in (page_config.visual_representations or [])
            ],
            sourcing_timeline_events=[
                SourcingTimelineEventResponse.model_validate(e)
                for e in (page_config.sourcing_timeline_events or [])
            ],
            completeness_warnings=completeness_warnings or [],
            event_type_warnings=event_type_warnings or [],
            unwind_option=unwind_option,
        )
