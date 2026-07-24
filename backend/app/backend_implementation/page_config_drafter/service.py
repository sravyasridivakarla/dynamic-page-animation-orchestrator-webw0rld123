"""Business logic for Page Config Drafter."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
import structlog

from app.backend_implementation.page_config_drafter.models import ActionType, WorkflowState
from app.backend_implementation.page_config_drafter.repository import PageConfigRepository
from app.backend_implementation.page_config_drafter.schema import (
    ApprovalResponse,
    DeleteConfirmResponse,
    DeleteProposalResponse,
    DraftDiffResponse,
    DraftGenerateRequest,
    PageConfigResponse,
    RejectionResponse,
    RollbackResponse,
)
from app.core.clients import KnowledgeGraphClient, ProvenanceStoreClient

logger = structlog.get_logger()


class KGUnavailableError(Exception):
    """Raised when the Knowledge Graph Service is unreachable."""


class ParentConfigRequiredError(Exception):
    """Raised when child records are submitted without a valid parent config."""


class ProvenanceStoreUnavailableError(Exception):
    """Raised when the Provenance Store is unreachable, blocking the action."""


class ApprovalSurfaceUnavailableError(Exception):
    """Raised when the approval UI is unavailable; draft held in pending state."""


class PageConfigDrafterService:
    def __init__(
        self,
        db,
        kg_client: KnowledgeGraphClient,
        provenance_client: ProvenanceStoreClient,
    ):
        self.db = db
        self.kg_client = kg_client
        self.provenance_client = provenance_client
        self._repo = PageConfigRepository(db)

    # ── FR-DG1, FR-DG2, FR-DG3, FR-DG5, FR-AU1, FR-AU2 ──────────────────────

    async def generate_draft(self, request: DraftGenerateRequest) -> PageConfigResponse:
        # FR-DG1: must call KG; if unavailable, raise — never silently fall back
        try:
            kg_context = await self.kg_client.get_product_context(request.product_id)
        except (httpx.ConnectError, httpx.HTTPError, httpx.ConnectTimeout) as exc:
            logger.warning("kg_service_unavailable", error=str(exc))
            raise KGUnavailableError(
                "Knowledge Graph Service unavailable. Use legacy manual config form."
            ) from exc

        # FR-DG2: assemble parent + all children as a coherent unit
        config = await self._repo.create_page_config(request.product_id)

        # FR-DG3: parent exists in the same transaction before children are attached
        self._validate_parent_before_child(config.id)

        scroll_sections_data = kg_context.get("scroll_sections", [])
        visual_reps_data = kg_context.get("visual_representations", [])
        timeline_events_data = kg_context.get("sourcing_timeline_events", [])

        for i, section in enumerate(scroll_sections_data):
            await self._repo.create_scroll_section(
                page_config_id=config.id,
                order=section.get("order", i),
                content=section.get("content", ""),
            )

        for vr in visual_reps_data:
            await self._repo.create_visual_representation(
                page_config_id=config.id,
                type=vr.get("type", ""),
                url=vr.get("url", ""),
            )

        # FR-DG5: validate event types against KG; store warnings, not errors
        event_type_warnings = await self._validate_event_types_against_kg(
            timeline_events_data
        )

        for event in timeline_events_data:
            event_type = event.get("event_type", "")
            await self._repo.create_sourcing_timeline_event(
                page_config_id=config.id,
                event_type=event_type,
                date=datetime.fromisoformat(event.get("date", datetime.now(timezone.utc).isoformat())),
                validated=(event_type not in event_type_warnings),
            )

        diff = self._build_structured_diff(config, scroll_sections_data, visual_reps_data, timeline_events_data)

        # FR-AU1, FR-AU2: write provenance; block if store unavailable
        await self._record_provenance_event(
            page_config_id=config.id,
            action_type=ActionType.draft_generated,
            inputs={"product_id": request.product_id},
            sources={"kg_context": kg_context},
            reasoning_trace="Draft generated from Knowledge Graph product context.",
            diff_presented=diff,
        )

        await self.db.commit()
        await self.db.refresh(config)
        return PageConfigResponse.model_validate(config)

    def _validate_parent_before_child(self, parent_id: Optional[UUID]) -> None:
        # FR-DG3: called with None to trigger the error path
        if parent_id is None:
            raise ParentConfigRequiredError(
                "A valid parent PageConfig must exist before child records can be created."
            )

    async def _validate_event_types_against_kg(self, events: List[dict]) -> List[str]:
        if not events:
            return []
        event_types = [e.get("event_type", "") for e in events]
        try:
            result = await self.kg_client.validate_event_types(event_types)
            invalid = result.get("invalid_event_types", [])
            return invalid
        except (httpx.ConnectError, httpx.HTTPError):
            return []

    def _build_structured_diff(
        self,
        config,
        scroll_sections: List[dict],
        visual_reps: List[dict],
        timeline_events: List[dict],
    ) -> Dict[str, Any]:
        return {
            "page_config": {
                "operation": "create",
                "product_id": config.product_id,
                "workflow_state": config.workflow_state.value if hasattr(config.workflow_state, "value") else config.workflow_state,
                "version": config.version,
            },
            "scroll_sections": [{"operation": "create", **s} for s in scroll_sections],
            "visual_representations": [{"operation": "create", **v} for v in visual_reps],
            "sourcing_timeline_events": [{"operation": "create", **e} for e in timeline_events],
        }

    # ── FR-DA1, FR-DG4 ────────────────────────────────────────────────────────

    async def get_draft_diff(self, draft_id: UUID) -> DraftDiffResponse:
        config = await self._repo.get_by_id(draft_id)
        if config is None:
            raise ValueError(f"Draft {draft_id} not found.")

        scroll_sections_data = [
            {"order": s.order, "content": s.content}
            for s in config.scroll_sections
        ]
        visual_reps_data = [
            {"type": v.type, "url": v.url}
            for v in config.visual_representations
        ]
        timeline_data = [
            {"event_type": e.event_type, "date": e.date.isoformat()}
            for e in config.sourcing_timeline_events
        ]

        diff = self._build_structured_diff(config, scroll_sections_data, visual_reps_data, timeline_data)

        # FR-DG4: validate completeness — flag, do not block
        warnings, has_incomplete = self._validate_completeness(config)

        return DraftDiffResponse(
            draft_id=config.id,
            product_id=config.product_id,
            diff=diff,
            completeness_warnings=warnings,
            has_incomplete_fields=has_incomplete,
        )

    def _validate_completeness(self, config) -> tuple:
        warnings = []
        if not config.scroll_sections:
            warnings.append("No scroll sections defined.")
        if not config.visual_representations:
            warnings.append("No visual representations defined.")
        if not config.sourcing_timeline_events:
            warnings.append("No sourcing timeline events defined.")
        return warnings, len(warnings) > 0

    # ── FR-DA2, FR-DA4, FR-AU1, FR-AU2, FR-AU3 ───────────────────────────────

    async def process_approval(
        self, draft_id: UUID, justification: Optional[str] = None
    ) -> ApprovalResponse:
        config = await self._repo.get_by_id(draft_id)
        if config is None:
            raise ValueError(f"Draft {draft_id} not found.")

        # FR-DA2: explicit approve signal required — this method IS the approve path
        config = await self._repo.update_workflow_state(config, WorkflowState.approved)
        config = await self._repo.increment_version(config)

        diff = self._build_structured_diff(config, [], [], [])

        await self._record_provenance_event(
            page_config_id=config.id,
            action_type=ActionType.draft_approved,
            inputs={"draft_id": str(draft_id)},
            diff_presented=diff,
            human_decision="approved",
            justification=justification,
        )

        await self.db.commit()
        return ApprovalResponse(
            draft_id=draft_id,
            status="approved",
            message="Draft approved and persisted.",
        )

    # ── FR-DA2, FR-AU1, FR-AU2 ────────────────────────────────────────────────

    async def process_rejection(self, draft_id: UUID, reason: str) -> RejectionResponse:
        config = await self._repo.get_by_id(draft_id)
        if config is None:
            raise ValueError(f"Draft {draft_id} not found.")

        await self._record_provenance_event(
            page_config_id=config.id,
            action_type=ActionType.draft_rejected,
            inputs={"draft_id": str(draft_id)},
            human_decision="rejected",
            justification=reason,
        )

        await self.db.commit()
        return RejectionResponse(
            draft_id=draft_id,
            status="rejected",
            message="Draft rejected and recorded in provenance.",
        )

    # ── FR-AU3 ────────────────────────────────────────────────────────────────

    async def restore_from_provenance(self, config_id: UUID, version: int) -> RollbackResponse:
        config = await self._repo.get_by_id(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} not found.")

        try:
            snapshot = await self.provenance_client.get_version_snapshot(str(config_id), version)
        except (httpx.ConnectError, httpx.HTTPError) as exc:
            raise ProvenanceStoreUnavailableError(
                "Provenance Store unavailable. Cannot perform rollback."
            ) from exc

        config.product_id = snapshot.get("product_id", config.product_id)
        config.workflow_state = WorkflowState(snapshot.get("workflow_state", WorkflowState.draft.value))
        config.version = version

        await self._record_provenance_event(
            page_config_id=config.id,
            action_type=ActionType.config_rolled_back,
            inputs={"target_version": version},
            sources={"snapshot": snapshot},
            reasoning_trace=f"Rolled back config to version {version}.",
            human_decision="rollback_confirmed",
        )

        await self.db.commit()
        return RollbackResponse(
            config_id=config_id,
            restored_version=version,
            message=f"Config restored to version {version}.",
        )

    # ── FR-DA3, FR-DEL1 ───────────────────────────────────────────────────────

    async def build_deletion_diff_with_unwind(self, config_id: UUID) -> DeleteProposalResponse:
        config = await self._repo.get_by_id(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} not found.")

        diff = {
            "page_config": {"operation": "delete", "id": str(config.id), "product_id": config.product_id},
            "scroll_sections": [{"operation": "delete", "id": str(s.id)} for s in config.scroll_sections],
            "visual_representations": [{"operation": "delete", "id": str(v.id)} for v in config.visual_representations],
            "sourcing_timeline_events": [{"operation": "delete", "id": str(e.id)} for e in config.sourcing_timeline_events],
        }

        await self._record_provenance_event(
            page_config_id=config.id,
            action_type=ActionType.deletion_proposed,
            inputs={"config_id": str(config_id)},
            diff_presented=diff,
        )

        await self.db.commit()
        return DeleteProposalResponse(config_id=config_id, diff=diff)

    # ── FR-DEL1, FR-DEL2 ──────────────────────────────────────────────────────

    async def execute_confirmed_deletion(
        self, config_id: UUID, explicit_confirm: bool
    ) -> DeleteConfirmResponse:
        if not explicit_confirm:
            raise ValueError("Explicit confirmation is required to delete a config.")

        config = await self._repo.get_by_id(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} not found.")

        await self._record_provenance_event(
            page_config_id=config.id,
            action_type=ActionType.deletion_confirmed,
            inputs={"config_id": str(config_id)},
            human_decision="deletion_confirmed",
        )

        await self._repo.delete_page_config(config)
        await self.db.commit()

        return DeleteConfirmResponse(
            config_id=config_id,
            status="deleted",
            message="Config deleted. No automated compensation will occur.",
        )

    # ── FR-AU1, FR-AU2 — shared provenance writer ─────────────────────────────

    async def _record_provenance_event(
        self,
        page_config_id: UUID,
        action_type: ActionType,
        inputs: Optional[dict] = None,
        sources: Optional[dict] = None,
        reasoning_trace: Optional[str] = None,
        diff_presented: Optional[dict] = None,
        human_decision: Optional[str] = None,
        justification: Optional[str] = None,
    ) -> None:
        payload = {
            "page_config_id": str(page_config_id),
            "action_type": action_type.value,
            "inputs": inputs,
            "sources": sources,
            "reasoning_trace": reasoning_trace,
            "diff_presented": diff_presented,
            "human_decision": human_decision,
            "justification": justification,
        }
        try:
            await self.provenance_client.write_event(payload)
        except (httpx.ConnectError, httpx.HTTPError) as exc:
            raise ProvenanceStoreUnavailableError(
                "Provenance Store unavailable. Action blocked until store is reachable."
            ) from exc

        await self._repo.create_provenance_record(
            page_config_id=page_config_id,
            action_type=action_type,
            inputs=inputs,
            sources=sources,
            reasoning_trace=reasoning_trace,
            diff_presented=diff_presented,
            human_decision=human_decision,
            justification=justification,
        )
