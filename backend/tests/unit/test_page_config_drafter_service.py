"""Unit tests for PageConfigService — all 13 FR acceptance criteria."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.backend_implementation.page_config_drafter.exceptions import (
    ConfigNotFoundError,
    InvalidDraftStateError,
    KnowledgeGraphUnavailableError,
    ParentNotFoundError,
    ProvenanceStoreUnavailableError,
)
from app.backend_implementation.page_config_drafter.models import (
    PageConfig,
    ScrollSection,
    SourcingTimelineEvent,
    VisualRepresentation,
)
from app.backend_implementation.page_config_drafter.schema import (
    DraftOperation,
    PageConfigDraft,
    ScrollSectionDraft,
    SourcingTimelineEventDraft,
    VisualRepresentationDraft,
    WorkflowState,
)
from app.backend_implementation.page_config_drafter.service import (
    PageConfigService,
    _draft_store,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRODUCT_ID = "product-123"
CONFIG_ID = uuid.uuid4()


def _make_kg_response(overrides: dict | None = None) -> MagicMock:
    data = {
        "page_title": "Test Product Page",
        "meta_description": "A great product",
        "layout_type": "STANDARD",
        "visibility_status": "DRAFT",
        "scroll_sections": [
            {"position": 1, "heading": "Section 1", "content": "Content 1"},
        ],
        "visual_representations": [
            {"type": "IMAGE", "url": "https://example.com/img.png", "position": 1},
        ],
        "sourcing_timeline_events": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "event_type": "SOURCED",
                "description": "Sourced from supplier",
            }
        ],
    }
    if overrides:
        data.update(overrides)
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = data
    return mock


def _make_event_types_response(types: list[str] | None = None) -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"event_types": [{"type": t} for t in (types or [])]}
    return mock


def _make_page_config(
    config_id: uuid.UUID | None = None,
    scroll_count: int = 1,
    vr_count: int = 1,
    event_count: int = 1,
) -> PageConfig:
    cid = config_id or CONFIG_ID
    cfg = MagicMock(spec=PageConfig)
    cfg.id = cid
    cfg.product_id = PRODUCT_ID
    cfg.page_title = "Old Title"
    cfg.meta_description = "Old description"
    cfg.layout_type = "STANDARD"
    cfg.visibility_status = "DRAFT"
    cfg.created_by = "user-1"
    cfg.updated_by = "user-1"

    scroll = MagicMock(spec=ScrollSection)
    scroll.id = uuid.uuid4()
    scroll.position = 1
    scroll.heading = "Section"
    scroll.content = "Content"
    scroll.background_image_url = None
    cfg.scroll_sections = [scroll] * scroll_count

    vr = MagicMock(spec=VisualRepresentation)
    vr.id = uuid.uuid4()
    vr.type = "IMAGE"
    vr.url = "https://example.com/img.png"
    vr.alt_text = None
    vr.position = 1
    cfg.visual_representations = [vr] * vr_count

    event = MagicMock(spec=SourcingTimelineEvent)
    event.id = uuid.uuid4()
    event.timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    event.event_type = "SOURCED"
    event.description = "Sourced"
    cfg.sourcing_timeline_events = [event] * event_count

    return cfg


def _make_service(
    repo: MagicMock | None = None,
    kg_client: AsyncMock | None = None,
    provenance_client: AsyncMock | None = None,
    db: AsyncMock | None = None,
) -> PageConfigService:
    return PageConfigService(
        repo=repo or MagicMock(),
        kg_client=kg_client or AsyncMock(),
        provenance_client=provenance_client or AsyncMock(),
        db=db or AsyncMock(),
    )


@pytest.fixture(autouse=True)
def clear_draft_store():
    _draft_store.clear()
    yield
    _draft_store.clear()


# ---------------------------------------------------------------------------
# FR-2.1.1
# ---------------------------------------------------------------------------

def test_fr2_1_1_generate_create_draft_populates_required_fields():
    kg = AsyncMock()
    kg.get.side_effect = [_make_kg_response(), _make_event_types_response(["SOURCED"])]
    svc = _make_service(kg_client=kg)

    result = asyncio.run(svc.generate_create_draft(PRODUCT_ID))

    assert result.draft.product_id == PRODUCT_ID
    assert result.draft.page_title == "Test Product Page"
    assert result.draft.meta_description == "A great product"
    assert result.draft.layout_type == "STANDARD"
    assert result.draft.visibility_status == "DRAFT"
    assert result.operation == DraftOperation.CREATE
    assert result.draft.workflow_state == WorkflowState.DRAFT_PENDING


def test_fr2_1_1_generate_create_draft_kg_unavailable_raises_retriable_error():
    import httpx as _httpx

    kg = AsyncMock()
    kg.get.side_effect = _httpx.RequestError("connection refused")
    svc = _make_service(kg_client=kg)

    with pytest.raises(KnowledgeGraphUnavailableError):
        asyncio.run(svc.generate_create_draft(PRODUCT_ID))


# ---------------------------------------------------------------------------
# FR-2.1.2
# ---------------------------------------------------------------------------

def test_fr2_1_2_approve_and_persist_draft_writes_to_database():
    prov = AsyncMock()
    prov_resp = MagicMock()
    prov_resp.raise_for_status = MagicMock()
    prov.post.return_value = prov_resp

    repo = MagicMock()
    persisted_cfg = _make_page_config()
    repo.create = AsyncMock(return_value=persisted_cfg)

    db = AsyncMock()

    svc = _make_service(repo=repo, provenance_client=prov, db=db)

    draft = PageConfigDraft(
        product_id=PRODUCT_ID,
        page_title="Test",
        meta_description="Desc",
        layout_type="STANDARD",
        visibility_status="DRAFT",
        workflow_state=WorkflowState.DRAFT_PENDING,
    )
    token = "test-token-create"
    _draft_store[token] = (DraftOperation.CREATE, draft)

    asyncio.run(svc.approve_and_persist_draft(token, True, "approver-1"))

    repo.create.assert_called_once()
    db.commit.assert_called_once()


def test_fr2_1_2_approve_and_persist_draft_logs_to_provenance_store():
    prov = AsyncMock()
    prov_resp = MagicMock()
    prov_resp.raise_for_status = MagicMock()
    prov.post.return_value = prov_resp

    repo = MagicMock()
    repo.create = AsyncMock(return_value=_make_page_config())
    db = AsyncMock()

    svc = _make_service(repo=repo, provenance_client=prov, db=db)

    draft = PageConfigDraft(
        product_id=PRODUCT_ID,
        page_title="Test",
        meta_description="Desc",
        layout_type="STANDARD",
        visibility_status="DRAFT",
        workflow_state=WorkflowState.DRAFT_PENDING,
    )
    token = "test-token-prov"
    _draft_store[token] = (DraftOperation.CREATE, draft)

    asyncio.run(svc.approve_and_persist_draft(token, True, "approver-2"))

    prov.post.assert_called_once()
    call_kwargs = prov.post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    assert body["action"] == "approve_draft"
    assert body["actor_id"] == "approver-2"
    assert "draft" in body


# ---------------------------------------------------------------------------
# FR-2.1.3
# ---------------------------------------------------------------------------

def test_fr2_1_3_generate_update_draft_shows_before_after_diff():
    # KG returns updated page_title; meta_description in KG matches the persisted value
    # so it must NOT appear in the diff.
    kg = AsyncMock()
    kg.get.return_value = _make_kg_response(
        {"page_title": "Updated Title", "meta_description": "Old description"}
    )

    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_make_page_config())

    svc = _make_service(repo=repo, kg_client=kg)

    result = asyncio.run(svc.generate_update_draft(CONFIG_ID, PRODUCT_ID))

    assert result.operation == DraftOperation.UPDATE
    assert "page_title" in result.changes
    assert result.changes["page_title"].before == "Old Title"
    assert result.changes["page_title"].after == "Updated Title"
    assert "meta_description" not in result.changes


# ---------------------------------------------------------------------------
# FR-2.1.4
# ---------------------------------------------------------------------------

def test_fr2_1_4_generate_delete_draft_includes_all_child_records():
    repo = MagicMock()
    repo.get_by_id = AsyncMock(
        return_value=_make_page_config(scroll_count=2, vr_count=3, event_count=1)
    )
    svc = _make_service(repo=repo)

    result = asyncio.run(svc.generate_delete_draft(CONFIG_ID))

    assert result.operation == DraftOperation.DELETE
    assert len(result.draft.scroll_sections) == 2
    assert len(result.draft.visual_representations) == 3
    assert len(result.draft.sourcing_timeline_events) == 1
    assert result.prior_state is not None
    assert "record" in result.changes


# ---------------------------------------------------------------------------
# FR-2.2.1
# ---------------------------------------------------------------------------

def test_fr2_2_1_create_draft_includes_scroll_sections():
    kg = AsyncMock()
    kg.get.side_effect = [
        _make_kg_response(
            {
                "scroll_sections": [
                    {"position": 1, "heading": "H1", "content": "C1"},
                    {"position": 2, "heading": "H2", "content": "C2"},
                ]
            }
        ),
        _make_event_types_response(),
    ]
    svc = _make_service(kg_client=kg)

    result = asyncio.run(svc.generate_create_draft(PRODUCT_ID))

    assert len(result.draft.scroll_sections) == 2
    assert result.draft.scroll_sections[0].heading == "H1"
    assert result.draft.scroll_sections[1].heading == "H2"


# ---------------------------------------------------------------------------
# FR-2.2.2
# ---------------------------------------------------------------------------

def test_fr2_2_2_create_draft_includes_visual_representations():
    kg = AsyncMock()
    kg.get.side_effect = [
        _make_kg_response(
            {
                "visual_representations": [
                    {"type": "IMAGE", "url": "https://a.com/1.png", "position": 1},
                    {"type": "VIDEO", "url": "https://a.com/v.mp4", "position": 2},
                ]
            }
        ),
        _make_event_types_response(),
    ]
    svc = _make_service(kg_client=kg)

    result = asyncio.run(svc.generate_create_draft(PRODUCT_ID))

    assert len(result.draft.visual_representations) == 2
    assert result.draft.visual_representations[0].type == "IMAGE"
    assert result.draft.visual_representations[1].type == "VIDEO"


# ---------------------------------------------------------------------------
# FR-2.2.3
# ---------------------------------------------------------------------------

def test_fr2_2_3_create_draft_validates_sourcing_timeline_event_types():
    kg = AsyncMock()
    kg.get.side_effect = [
        _make_kg_response(
            {
                "sourcing_timeline_events": [
                    {
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "event_type": "UNKNOWN_TYPE",
                        "description": "An event",
                    }
                ]
            }
        ),
        _make_event_types_response(["SOURCED", "SHIPPED"]),
    ]
    svc = _make_service(kg_client=kg)

    result = asyncio.run(svc.generate_create_draft(PRODUCT_ID))

    assert any("UNKNOWN_TYPE" in w for w in result.draft.validation_warnings)
    assert len(result.draft.sourcing_timeline_events) == 1


# ---------------------------------------------------------------------------
# FR-2.3.1 — API layer test
# ---------------------------------------------------------------------------

def test_fr2_3_1_diff_response_includes_kg_sources_and_reasoning_trace():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.auth import get_current_user
    from app.core.database import get_db

    mock_kg = AsyncMock()
    mock_kg.get.side_effect = [
        _make_kg_response(),
        _make_event_types_response(["SOURCED"]),
    ]
    mock_provenance = AsyncMock()

    app.state.kg_client = mock_kg
    app.state.provenance_client = mock_provenance

    async def _override_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: {"sub": "test-user"}
    app.dependency_overrides[get_db] = _override_db

    try:
        client = TestClient(app, raise_server_exceptions=True)
        response = client.post(
            "/v1/page-configs/draft",
            json={"product_id": PRODUCT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert "kg_sources" in data
        assert "reasoning_trace" in data
        assert len(data["kg_sources"]) > 0
        assert data["reasoning_trace"] != ""
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# FR-2.3.2
# ---------------------------------------------------------------------------

def test_fr2_3_2_rollback_restores_prior_config_version():
    to_version = uuid.uuid4()
    restored_cfg = _make_page_config()

    prov = AsyncMock()
    version_resp = MagicMock()
    version_resp.raise_for_status = MagicMock()
    version_resp.json.return_value = {
        "draft": {
            "page_title": "Restored Title",
            "meta_description": "Restored desc",
            "layout_type": "HERO",
            "visibility_status": "PUBLISHED",
        }
    }
    rollback_log_resp = MagicMock()
    rollback_log_resp.raise_for_status = MagicMock()
    prov.get.return_value = version_resp
    prov.post.return_value = rollback_log_resp

    repo = MagicMock()
    repo.update = AsyncMock(return_value=restored_cfg)

    db = AsyncMock()

    svc = _make_service(repo=repo, provenance_client=prov, db=db)

    result_id, result_status = asyncio.run(
        svc.rollback_to_version(CONFIG_ID, to_version, "actor-1")
    )

    repo.update.assert_called_once()
    assert result_status == "RESTORED"
    db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# FR-2.4.1
# ---------------------------------------------------------------------------

def test_fr2_4_1_draft_with_missing_required_field_includes_warning():
    kg = AsyncMock()
    kg.get.side_effect = [
        _make_kg_response({"page_title": ""}),
        _make_event_types_response(),
    ]
    svc = _make_service(kg_client=kg)

    result = asyncio.run(svc.generate_create_draft(PRODUCT_ID))

    assert any("page_title" in w for w in result.draft.validation_warnings)
    assert result.approval_token in _draft_store


# ---------------------------------------------------------------------------
# FR-2.4.2
# ---------------------------------------------------------------------------

def test_fr2_4_2_approve_draft_without_parent_raises_parent_not_found_error():
    prov = AsyncMock()
    prov_resp = MagicMock()
    prov_resp.raise_for_status = MagicMock()
    prov.post.return_value = prov_resp

    repo = MagicMock()
    repo.update = AsyncMock(side_effect=ConfigNotFoundError(CONFIG_ID))

    db = AsyncMock()

    svc = _make_service(repo=repo, provenance_client=prov, db=db)

    draft = PageConfigDraft(
        id=CONFIG_ID,
        product_id=PRODUCT_ID,
        page_title="Test",
        meta_description="Desc",
        layout_type="STANDARD",
        visibility_status="DRAFT",
        workflow_state=WorkflowState.DRAFT_PENDING,
    )
    token = "test-token-update-notfound"
    _draft_store[token] = (DraftOperation.UPDATE, draft)

    with pytest.raises(ParentNotFoundError):
        asyncio.run(svc.approve_and_persist_draft(token, True, "approver-3"))
