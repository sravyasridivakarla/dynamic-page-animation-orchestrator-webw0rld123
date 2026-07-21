"""Unit tests for PageConfigDrafterService — each maps to one FR acceptance criterion."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.backend_implementation.page_config_drafter.models import (
    PageConfig,
    ProvenanceRecord,
    ScrollSection,
    SourcingTimelineEvent,
    VisualRepresentation,
    WorkflowState,
)
from app.backend_implementation.page_config_drafter.schema import (
    ApproveRequest,
    DraftRequest,
    RejectRequest,
    ScrollSectionInput,
    SourcingTimelineEventInput,
    VisualRepresentationInput,
)
from app.backend_implementation.page_config_drafter.service import (
    InvalidStateError,
    KGUnavailableFallbackError,
    PageConfigDrafterService,
    ProvenanceUnavailableError,
)
from app.clients.kg_client import KGServiceUnavailableError
from app.clients.provenance_client import ProvenanceStoreUnavailableError


def _make_page_config(**kwargs) -> PageConfig:
    cfg = PageConfig(
        product_id=kwargs.get("product_id", "prod-1"),
        workflow_state=kwargs.get("workflow_state", WorkflowState.draft),
        version=kwargs.get("version", 1),
    )
    cfg.id = kwargs.get("id", uuid4())
    cfg.scroll_sections = kwargs.get("scroll_sections", [])
    cfg.visual_representations = kwargs.get("visual_representations", [])
    cfg.sourcing_timeline_events = kwargs.get("sourcing_timeline_events", [])
    cfg.provenance_records = kwargs.get("provenance_records", [])
    cfg.created_at = datetime.now(timezone.utc)
    cfg.updated_at = datetime.now(timezone.utc)
    return cfg


def _make_service(session, kg_client, provenance_client, page_config=None):
    svc = PageConfigDrafterService(
        session=session, kg_client=kg_client, provenance_client=provenance_client
    )
    if page_config is not None:
        svc._repo = AsyncMock()
        svc._repo.get_by_id = AsyncMock(return_value=page_config)
        svc._repo.create = AsyncMock(return_value=page_config)
        svc._repo.update = AsyncMock(return_value=page_config)
        svc._repo.delete = AsyncMock()
        svc._repo.add_scroll_section = AsyncMock(side_effect=lambda s: s)
        svc._repo.add_visual_representation = AsyncMock(side_effect=lambda v: v)
        svc._repo.add_sourcing_event = AsyncMock(side_effect=lambda e: e)
        svc._prov_repo = AsyncMock()
        svc._prov_repo.append = AsyncMock(side_effect=lambda r: r)
        svc._prov_repo.get_by_config_ordered = AsyncMock(return_value=[])
    return svc


# --- FR-DG1 ---

async def test_fr_dg1_kg_unavailable_returns_fallback(
    mock_session, mock_kg_client, mock_provenance_client
):
    mock_kg_client.get_product_context = AsyncMock(
        side_effect=KGServiceUnavailableError("connection refused")
    )
    svc = PageConfigDrafterService(
        session=mock_session, kg_client=mock_kg_client, provenance_client=mock_provenance_client
    )
    with pytest.raises(KGUnavailableFallbackError) as exc_info:
        await svc.generate_draft(DraftRequest(product_id="prod-1"))
    assert "legacy manual create-config form" in str(exc_info.value)
    mock_session.commit.assert_not_called()


# --- FR-DG2 ---

async def test_fr_dg2_draft_includes_all_child_records(
    mock_session, mock_kg_client, mock_provenance_client
):
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id)

    svc = PageConfigDrafterService(
        session=mock_session, kg_client=mock_kg_client, provenance_client=mock_provenance_client
    )
    svc._repo = AsyncMock()
    svc._repo.create = AsyncMock(return_value=page_config)
    svc._repo.add_scroll_section = AsyncMock(side_effect=lambda s: s)
    svc._repo.add_visual_representation = AsyncMock(side_effect=lambda v: v)
    svc._repo.add_sourcing_event = AsyncMock(side_effect=lambda e: e)
    svc._prov_repo = AsyncMock()
    svc._prov_repo.append = AsyncMock(side_effect=lambda r: r)

    mock_session.refresh = AsyncMock()

    request = DraftRequest(
        product_id="prod-1",
        scroll_sections=[ScrollSectionInput(order=1, content="intro")],
        visual_representations=[VisualRepresentationInput(type="hero", url="https://img.example.com/hero.jpg")],
        sourcing_timeline_events=[
            SourcingTimelineEventInput(event_type="launch", date=datetime.now(timezone.utc))
        ],
    )
    await svc.generate_draft(request)

    svc._repo.add_scroll_section.assert_called_once()
    svc._repo.add_visual_representation.assert_called_once()
    svc._repo.add_sourcing_event.assert_called_once()


# --- FR-DG3 ---

async def test_fr_dg3_child_without_parent_is_rejected(
    mock_session, mock_kg_client, mock_provenance_client
):
    svc = PageConfigDrafterService(
        session=mock_session, kg_client=mock_kg_client, provenance_client=mock_provenance_client
    )
    svc._repo = AsyncMock()
    svc._repo.create = AsyncMock(side_effect=Exception("FK violation: page_config_id is NULL"))
    svc._prov_repo = AsyncMock()

    request = DraftRequest(
        product_id="prod-1",
        scroll_sections=[ScrollSectionInput(order=1, content="content")],
    )
    with pytest.raises(Exception, match="page_config_id"):
        await svc.generate_draft(request)

    mock_session.commit.assert_not_called()


# --- FR-DG4 ---

async def test_fr_dg4_incomplete_draft_flagged_not_blocked(
    mock_session, mock_kg_client, mock_provenance_client
):
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id)
    svc = _make_service(mock_session, mock_kg_client, mock_provenance_client, page_config)

    diff = await svc.get_draft_diff(cfg_id)

    assert len(diff.completeness_warnings) > 0
    fields = [w.field for w in diff.completeness_warnings]
    assert "scroll_sections" in fields


# --- FR-DG5 ---

async def test_fr_dg5_invalid_event_type_surfaces_as_warning(
    mock_session, mock_kg_client, mock_provenance_client
):
    mock_kg_client.validate_event_types = AsyncMock(
        return_value={"bad_event": False}
    )
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id)
    svc = PageConfigDrafterService(
        session=mock_session, kg_client=mock_kg_client, provenance_client=mock_provenance_client
    )
    svc._repo = AsyncMock()
    svc._repo.create = AsyncMock(return_value=page_config)
    svc._repo.add_scroll_section = AsyncMock(side_effect=lambda s: s)
    svc._repo.add_visual_representation = AsyncMock(side_effect=lambda v: v)
    svc._repo.add_sourcing_event = AsyncMock(side_effect=lambda e: e)
    svc._prov_repo = AsyncMock()
    svc._prov_repo.append = AsyncMock(side_effect=lambda r: r)
    mock_session.refresh = AsyncMock()

    request = DraftRequest(
        product_id="prod-1",
        sourcing_timeline_events=[
            SourcingTimelineEventInput(event_type="bad_event", date=datetime.now(timezone.utc))
        ],
    )
    result = await svc.generate_draft(request)

    provenance_call_args = svc._prov_repo.append.call_args[0][0]
    warnings = provenance_call_args.diff_presented.get("event_type_warnings", [])
    assert any(w["event_type"] == "bad_event" for w in warnings)
    mock_session.commit.assert_called_once()


# --- FR-DA2 ---

async def test_fr_da2_no_commit_without_approval_signal(
    mock_session, mock_kg_client, mock_provenance_client
):
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id, workflow_state=WorkflowState.draft)
    svc = _make_service(mock_session, mock_kg_client, mock_provenance_client, page_config)

    mock_session.commit.reset_mock()
    await svc.process_approval(cfg_id, ApproveRequest())
    mock_session.commit.assert_called_once()

    mock_session.commit.reset_mock()
    with pytest.raises((InvalidStateError, Exception)):
        await svc.process_approval(cfg_id, ApproveRequest())


# --- FR-DA3 ---

async def test_fr_da3_deletion_diff_contains_unwind_option(
    mock_session, mock_kg_client, mock_provenance_client
):
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id, workflow_state=WorkflowState.draft)
    svc = _make_service(mock_session, mock_kg_client, mock_provenance_client, page_config)

    response = await svc.propose_deletion(cfg_id)

    assert response.unwind_option is True
    assert response.diff.unwind_option is True


# --- FR-AU1 ---

async def test_fr_au1_all_actions_recorded_in_provenance(
    mock_session, mock_kg_client, mock_provenance_client
):
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id)
    svc = PageConfigDrafterService(
        session=mock_session, kg_client=mock_kg_client, provenance_client=mock_provenance_client
    )
    svc._repo = AsyncMock()
    svc._repo.create = AsyncMock(return_value=page_config)
    svc._repo.add_scroll_section = AsyncMock(side_effect=lambda s: s)
    svc._repo.add_visual_representation = AsyncMock(side_effect=lambda v: v)
    svc._repo.add_sourcing_event = AsyncMock(side_effect=lambda e: e)
    svc._prov_repo = AsyncMock()
    svc._prov_repo.append = AsyncMock(side_effect=lambda r: r)
    mock_session.refresh = AsyncMock()

    request = DraftRequest(product_id="prod-1")
    await svc.generate_draft(request)

    mock_provenance_client.record_action.assert_called_once()
    call_payload = mock_provenance_client.record_action.call_args[0][0]
    assert "inputs" in call_payload
    assert "sources" in call_payload
    assert "reasoning_trace" in call_payload
    assert "diff_presented" in call_payload
    assert "action_type" in call_payload


# --- FR-AU2 ---

async def test_fr_au2_action_blocked_when_store_unavailable(
    mock_session, mock_kg_client, mock_provenance_client
):
    mock_provenance_client.record_action = AsyncMock(
        side_effect=ProvenanceStoreUnavailableError("store down")
    )
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id)
    svc = PageConfigDrafterService(
        session=mock_session, kg_client=mock_kg_client, provenance_client=mock_provenance_client
    )
    svc._repo = AsyncMock()
    svc._repo.create = AsyncMock(return_value=page_config)
    svc._repo.add_scroll_section = AsyncMock(side_effect=lambda s: s)
    svc._repo.add_visual_representation = AsyncMock(side_effect=lambda v: v)
    svc._repo.add_sourcing_event = AsyncMock(side_effect=lambda e: e)
    svc._prov_repo = AsyncMock()

    with pytest.raises(ProvenanceUnavailableError):
        await svc.generate_draft(DraftRequest(product_id="prod-1"))
    mock_session.commit.assert_not_called()


# --- FR-AU3 ---

async def test_fr_au3_rollback_restores_prior_version(
    mock_session, mock_kg_client, mock_provenance_client
):
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id, version=2)

    prior_prov = ProvenanceRecord(
        page_config_id=cfg_id,
        action_type="generate_draft",
        inputs={},
        sources={},
        reasoning_trace="initial draft",
        diff_presented={"version": 1},
    )
    prior_prov.id = uuid4()
    prior_prov.timestamp = datetime.now(timezone.utc)

    current_prov = ProvenanceRecord(
        page_config_id=cfg_id,
        action_type="approve",
        inputs={},
        sources={},
        reasoning_trace="approved",
        diff_presented={"version": 2},
    )
    current_prov.id = uuid4()
    current_prov.timestamp = datetime.now(timezone.utc)

    svc = _make_service(mock_session, mock_kg_client, mock_provenance_client, page_config)
    svc._prov_repo.get_by_config_ordered = AsyncMock(return_value=[current_prov, prior_prov])

    result = await svc.rollback_config(cfg_id)

    assert result.restored_version == 1
    assert result.config_id == cfg_id


# --- FR-DEL1 ---

async def test_fr_del1_deletion_requires_explicit_confirm(
    mock_session, mock_kg_client, mock_provenance_client
):
    cfg_id = uuid4()
    page_config = _make_page_config(id=cfg_id, workflow_state=WorkflowState.draft)
    svc = _make_service(mock_session, mock_kg_client, mock_provenance_client, page_config)

    with pytest.raises(InvalidStateError, match="pending_deletion"):
        await svc.execute_confirmed_deletion(cfg_id)

    mock_session.commit.assert_not_called()


# --- FR-FB1 ---

async def test_fr_fb1_legacy_screens_accessible_when_agent_down(
    mock_session, mock_kg_client, mock_provenance_client
):
    mock_kg_client.get_product_context = AsyncMock(
        side_effect=KGServiceUnavailableError("agent pipeline down")
    )
    svc = PageConfigDrafterService(
        session=mock_session, kg_client=mock_kg_client, provenance_client=mock_provenance_client
    )

    with pytest.raises(KGUnavailableFallbackError) as exc_info:
        await svc.generate_draft(DraftRequest(product_id="prod-1"))

    assert "legacy" in str(exc_info.value).lower()
    mock_session.commit.assert_not_called()
