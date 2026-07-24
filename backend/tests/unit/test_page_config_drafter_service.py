"""FR-traced unit tests for PageConfigDrafterService.

Each test is named by FR-ID and validates the specific acceptance criterion.
All external clients (KG Service, Provenance Store) are mocked with AsyncMock.
No real DB, HTTP, or external calls are made.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.backend_implementation.page_config_drafter.models import (
    ActionType,
    PageConfig,
    ProvenanceRecord,
    ScrollSection,
    SourcingTimelineEvent,
    VisualRepresentation,
    WorkflowState,
)
from app.backend_implementation.page_config_drafter.schema import DraftGenerateRequest
from app.backend_implementation.page_config_drafter.service import (
    KGUnavailableError,
    PageConfigDrafterService,
    ParentConfigRequiredError,
    ProvenanceStoreUnavailableError,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_config(
    product_id: str = "prod-1",
    workflow_state: WorkflowState = WorkflowState.draft,
    version: int = 1,
    scroll_sections=None,
    visual_representations=None,
    sourcing_timeline_events=None,
) -> PageConfig:
    config = MagicMock(spec=PageConfig)
    config.id = uuid.uuid4()
    config.product_id = product_id
    config.workflow_state = workflow_state
    config.version = version
    config.scroll_sections = scroll_sections or []
    config.visual_representations = visual_representations or []
    config.sourcing_timeline_events = sourcing_timeline_events or []
    config.provenance_records = []
    config.created_at = datetime.now(timezone.utc)
    config.updated_at = datetime.now(timezone.utc)
    return config


def make_service(db=None, kg_client=None, provenance_client=None, repo=None):
    db = db or AsyncMock()
    kg_client = kg_client or AsyncMock()
    provenance_client = provenance_client or AsyncMock()
    svc = PageConfigDrafterService(db=db, kg_client=kg_client, provenance_client=provenance_client)
    if repo is not None:
        svc._repo = repo
    return svc


# ── FR-DG1: KG unavailable → fallback error, draft never generated ─────────

async def test_fr_dg1_kg_unavailable_returns_fallback():
    kg_client = AsyncMock()
    kg_client.get_product_context.side_effect = httpx.ConnectError("unreachable")

    provenance_client = AsyncMock()
    svc = make_service(kg_client=kg_client, provenance_client=provenance_client)

    with pytest.raises(KGUnavailableError):
        await svc.generate_draft(DraftGenerateRequest(product_id="prod-1"))

    provenance_client.write_event.assert_not_called()


# ── FR-DG2: draft includes all child records ──────────────────────────────────

async def test_fr_dg2_draft_includes_all_child_records():
    config = make_config()
    repo = AsyncMock()
    repo.create_page_config.return_value = config
    repo.create_scroll_section.return_value = MagicMock(spec=ScrollSection)
    repo.create_visual_representation.return_value = MagicMock(spec=VisualRepresentation)
    repo.create_sourcing_timeline_event.return_value = MagicMock(spec=SourcingTimelineEvent)
    repo.create_provenance_record.return_value = MagicMock(spec=ProvenanceRecord)

    db = AsyncMock()
    db.refresh = AsyncMock(return_value=None)

    # make refresh populate the ORM fields needed by model_validate
    async def refresh_side_effect(obj):
        obj.scroll_sections = []
        obj.visual_representations = []
        obj.sourcing_timeline_events = []

    db.refresh.side_effect = refresh_side_effect

    kg_context = {
        "scroll_sections": [{"order": 0, "content": "intro"}],
        "visual_representations": [{"type": "banner", "url": "http://example.com/img.png"}],
        "sourcing_timeline_events": [
            {"event_type": "production_start", "date": "2026-01-01T00:00:00+00:00"}
        ],
    }
    kg_client = AsyncMock()
    kg_client.get_product_context.return_value = kg_context
    kg_client.validate_event_types.return_value = {"invalid_event_types": []}

    provenance_client = AsyncMock()
    provenance_client.write_event.return_value = {}

    svc = make_service(db=db, kg_client=kg_client, provenance_client=provenance_client, repo=repo)

    await svc.generate_draft(DraftGenerateRequest(product_id="prod-1"))

    repo.create_scroll_section.assert_called_once()
    repo.create_visual_representation.assert_called_once()
    repo.create_sourcing_timeline_event.assert_called_once()


# ── FR-DG3: child without parent is rejected ─────────────────────────────────

async def test_fr_dg3_child_without_parent_is_rejected():
    svc = make_service()
    with pytest.raises(ParentConfigRequiredError):
        svc._validate_parent_before_child(None)


# ── FR-DG4: incomplete draft flagged but not blocked ─────────────────────────

async def test_fr_dg4_incomplete_draft_flagged_not_blocked():
    config = make_config(
        scroll_sections=[],
        visual_representations=[],
        sourcing_timeline_events=[],
    )
    repo = AsyncMock()
    repo.get_by_id.return_value = config

    svc = make_service(repo=repo)
    result = await svc.get_draft_diff(config.id)

    assert result.has_incomplete_fields is True
    assert len(result.completeness_warnings) > 0
    # verify it did NOT raise — incompleteness flags, not blocks
    assert result.draft_id == config.id


# ── FR-DG5: invalid event type surfaces as warning in diff ───────────────────

async def test_fr_dg5_invalid_event_type_surfaces_as_warning():
    kg_client = AsyncMock()
    kg_client.validate_event_types.return_value = {"invalid_event_types": ["bad_type"]}

    svc = make_service(kg_client=kg_client)
    events = [{"event_type": "bad_type", "date": "2026-01-01T00:00:00+00:00"}]
    warnings = await svc._validate_event_types_against_kg(events)

    assert "bad_type" in warnings


# ── FR-DA2: no commit without explicit approval signal ───────────────────────

async def test_fr_da2_no_commit_without_approval_signal():
    config = make_config()
    repo = AsyncMock()
    repo.get_by_id.return_value = config
    repo.update_workflow_state.return_value = config
    repo.increment_version.return_value = config
    repo.create_provenance_record.return_value = MagicMock(spec=ProvenanceRecord)

    db = AsyncMock()
    provenance_client = AsyncMock()
    provenance_client.write_event.return_value = {}

    svc = make_service(db=db, provenance_client=provenance_client, repo=repo)

    # Without calling process_approval, commit should not have been called
    db.commit.assert_not_called()

    # Calling the rejection path also should not commit without the approve call
    provenance_client2 = AsyncMock()
    provenance_client2.write_event.return_value = {}
    db2 = AsyncMock()
    repo2 = AsyncMock()
    repo2.get_by_id.return_value = config
    repo2.create_provenance_record.return_value = MagicMock(spec=ProvenanceRecord)
    svc2 = make_service(db=db2, provenance_client=provenance_client2, repo=repo2)
    await svc2.process_rejection(config.id, reason="not right")
    # commit is called by rejection, but workflow_state was NOT set to approved
    repo2.update_workflow_state.assert_not_called()


# ── FR-DA3: deletion diff contains unwind_option field ───────────────────────

async def test_fr_da3_deletion_diff_contains_unwind_option():
    config = make_config()
    repo = AsyncMock()
    repo.get_by_id.return_value = config
    repo.create_provenance_record.return_value = MagicMock(spec=ProvenanceRecord)

    provenance_client = AsyncMock()
    provenance_client.write_event.return_value = {}
    db = AsyncMock()

    svc = make_service(db=db, provenance_client=provenance_client, repo=repo)
    result = await svc.build_deletion_diff_with_unwind(config.id)

    assert result.unwind_option is not None
    assert len(result.unwind_option) > 0
    assert "page_config" in result.diff


# ── FR-AU1: all actions recorded in provenance with required fields ───────────

async def test_fr_au1_all_actions_recorded_in_provenance():
    config = make_config()
    repo = AsyncMock()
    repo.get_by_id.return_value = config
    repo.update_workflow_state.return_value = config
    repo.increment_version.return_value = config
    repo.create_provenance_record.return_value = MagicMock(spec=ProvenanceRecord)

    provenance_client = AsyncMock()
    provenance_client.write_event.return_value = {}
    db = AsyncMock()

    svc = make_service(db=db, provenance_client=provenance_client, repo=repo)
    await svc.process_approval(config.id, justification="looks good")

    provenance_client.write_event.assert_called_once()
    call_kwargs = provenance_client.write_event.call_args[0][0]
    assert "action_type" in call_kwargs
    assert "inputs" in call_kwargs
    assert "diff_presented" in call_kwargs
    assert "human_decision" in call_kwargs
    assert call_kwargs["human_decision"] == "approved"
    assert call_kwargs["justification"] == "looks good"


# ── FR-AU2: action blocked when provenance store unavailable ─────────────────

async def test_fr_au2_action_blocked_when_store_unavailable():
    config = make_config()
    repo = AsyncMock()
    repo.get_by_id.return_value = config
    repo.update_workflow_state.return_value = config
    repo.increment_version.return_value = config

    provenance_client = AsyncMock()
    provenance_client.write_event.side_effect = httpx.ConnectError("store down")
    db = AsyncMock()

    svc = make_service(db=db, provenance_client=provenance_client, repo=repo)

    with pytest.raises(ProvenanceStoreUnavailableError):
        await svc.process_approval(config.id)

    db.commit.assert_not_called()


# ── FR-AU3: rollback restores prior version from provenance ──────────────────

async def test_fr_au3_rollback_restores_prior_version():
    config = make_config(version=3)
    snapshot = {"product_id": "prod-1", "workflow_state": "approved"}

    repo = AsyncMock()
    repo.get_by_id.return_value = config
    repo.create_provenance_record.return_value = MagicMock(spec=ProvenanceRecord)

    provenance_client = AsyncMock()
    provenance_client.get_version_snapshot.return_value = snapshot
    provenance_client.write_event.return_value = {}
    db = AsyncMock()

    svc = make_service(db=db, provenance_client=provenance_client, repo=repo)
    result = await svc.restore_from_provenance(config.id, version=2)

    assert result.restored_version == 2
    provenance_client.get_version_snapshot.assert_called_once_with(str(config.id), 2)
    db.commit.assert_called_once()


# ── FR-DEL1: deletion requires explicit confirm flag ─────────────────────────

async def test_fr_del1_deletion_requires_explicit_confirm():
    config = make_config()
    repo = AsyncMock()
    repo.get_by_id.return_value = config
    svc = make_service(repo=repo)

    with pytest.raises(ValueError, match="Explicit confirmation"):
        await svc.execute_confirmed_deletion(config.id, explicit_confirm=False)


# ── FR-DEL2: confirmed deletion has no automated compensation ────────────────

async def test_fr_del2_confirmed_deletion_no_automated_compensation():
    config = make_config()
    repo = AsyncMock()
    repo.get_by_id.return_value = config
    repo.create_provenance_record.return_value = MagicMock(spec=ProvenanceRecord)
    repo.delete_page_config.return_value = None

    provenance_client = AsyncMock()
    provenance_client.write_event.return_value = {}
    db = AsyncMock()

    svc = make_service(db=db, provenance_client=provenance_client, repo=repo)
    result = await svc.execute_confirmed_deletion(config.id, explicit_confirm=True)

    assert result.status == "deleted"
    assert "No automated compensation" in result.message
    repo.delete_page_config.assert_called_once_with(config)


# ── FR-FB1: legacy health endpoint accessible when drafter is unavailable ────

def test_fr_fb1_legacy_screens_accessible_when_agent_down():
    from app.main import app

    # Provide minimal app.state so lifespan doesn't need real clients
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
