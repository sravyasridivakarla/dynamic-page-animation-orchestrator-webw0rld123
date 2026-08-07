"""Unit tests for PageConfigService covering all functional requirements."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import app.backend_implementation.page_config_drafter.service as svc_module
from app.backend_implementation.page_config_drafter.exceptions import (
    ConfigNotFoundError,
    InvalidDraftStateError,
    KnowledgeGraphUnavailableError,
    ParentNotFoundError,
    ProvenanceStoreUnavailableError,
)
from app.backend_implementation.page_config_drafter.schema import (
    DiffOperation,
    PageConfigDraft,
    WorkflowState,
)
from app.backend_implementation.page_config_drafter.service import PageConfigService


@pytest.fixture(autouse=True)
def clear_draft_store():
    svc_module._draft_store.clear()
    yield
    svc_module._draft_store.clear()


@pytest.fixture
def kg_client():
    return MagicMock()


@pytest.fixture
def provenance_client():
    return MagicMock()


@pytest.fixture
def repository():
    return MagicMock()


@pytest.fixture
def session():
    s = AsyncMock()
    return s


@pytest.fixture
def service(session, repository, kg_client, provenance_client):
    return PageConfigService(
        session=session,
        repository=repository,
        kg_client=kg_client,
        provenance_client=provenance_client,
    )


def _make_kg_response(data: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    return response


def _make_event_types_response(event_types: list) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"event_types": event_types}
    response.raise_for_status = MagicMock()
    return response


def _make_orm_config(
    config_id=None,
    product_id="prod-123",
    page_title="Test Page",
    meta_description="A test description",
    layout_type_value="STANDARD",
    visibility_status_value="DRAFT",
    scroll_sections=None,
    visual_representations=None,
    sourcing_timeline_events=None,
):
    from app.backend_implementation.page_config_drafter.models import (
        LayoutType,
        VisibilityStatus,
    )

    config = MagicMock()
    config.id = config_id or uuid4()
    config.product_id = product_id
    config.page_title = page_title
    config.meta_description = meta_description
    config.layout_type = LayoutType(layout_type_value)
    config.visibility_status = VisibilityStatus(visibility_status_value)
    config.created_at = datetime.now(timezone.utc)
    config.updated_at = datetime.now(timezone.utc)
    config.created_by = "user-1"
    config.updated_by = "user-1"
    config.scroll_sections = scroll_sections or []
    config.visual_representations = visual_representations or []
    config.sourcing_timeline_events = sourcing_timeline_events or []
    return config


async def test_fr2_1_1_generate_create_draft_populates_required_fields(service, kg_client):
    kg_client.get = AsyncMock(
        side_effect=[
            _make_kg_response({
                "name": "Test Product",
                "meta_description": "A test product",
                "layout_type": "HERO",
                "visibility_status": "DRAFT",
                "scroll_sections": [],
                "visual_representations": [],
                "sourcing_timeline_events": [],
            }),
            _make_event_types_response(["PRODUCTION", "SOURCING"]),
        ]
    )

    result = await service.generate_create_draft("prod-123")

    assert result.draft.product_id == "prod-123"
    assert result.draft.page_title == "Test Product"
    assert result.draft.meta_description == "A test product"
    assert result.draft.layout_type == "HERO"
    assert result.draft.visibility_status == "DRAFT"
    assert result.draft.workflow_state == WorkflowState.DRAFT_PENDING
    assert result.operation == DiffOperation.CREATE
    assert result.approval_token


async def test_fr2_1_1_generate_create_draft_kg_unavailable_raises_retriable_error(
    service, kg_client
):
    kg_client.get = AsyncMock(side_effect=Exception("Connection refused"))

    with pytest.raises(KnowledgeGraphUnavailableError):
        await service.generate_create_draft("prod-123")


async def test_fr2_1_2_approve_and_persist_draft_writes_to_database(
    service, repository, session, provenance_client
):
    approval_token = str(uuid4())
    draft = PageConfigDraft(
        product_id="prod-123",
        page_title="Test Page",
        meta_description="Description",
        layout_type="STANDARD",
        visibility_status="DRAFT",
        workflow_state=WorkflowState.DRAFT_PENDING,
    )
    svc_module._draft_store[approval_token] = {
        "draft": draft,
        "operation": DiffOperation.CREATE,
        "config_id": None,
    }

    mock_persisted = MagicMock()
    mock_persisted.id = uuid4()
    repository.create = AsyncMock(return_value=mock_persisted)

    prov_response = MagicMock()
    prov_response.raise_for_status = MagicMock()
    provenance_client.post = AsyncMock(return_value=prov_response)

    result = await service.approve_and_persist_draft(approval_token, "user-123")

    repository.create.assert_called_once()
    session.commit.assert_called_once()
    assert result.status == "PERSISTED"
    assert result.id == mock_persisted.id


async def test_fr2_1_2_approve_and_persist_draft_logs_to_provenance_store(
    service, repository, session, provenance_client
):
    approval_token = str(uuid4())
    draft = PageConfigDraft(
        product_id="prod-123",
        page_title="Test Page",
        meta_description="Description",
        layout_type="STANDARD",
        visibility_status="DRAFT",
        workflow_state=WorkflowState.DRAFT_PENDING,
    )
    svc_module._draft_store[approval_token] = {
        "draft": draft,
        "operation": DiffOperation.CREATE,
        "config_id": None,
    }

    mock_persisted = MagicMock()
    mock_persisted.id = uuid4()
    repository.create = AsyncMock(return_value=mock_persisted)

    prov_response = MagicMock()
    prov_response.raise_for_status = MagicMock()
    provenance_client.post = AsyncMock(return_value=prov_response)

    await service.approve_and_persist_draft(approval_token, "user-123")

    provenance_client.post.assert_called_once()
    call_kwargs = provenance_client.post.call_args
    assert call_kwargs[0][0] == "/audit"
    payload = call_kwargs[1]["json"]
    assert payload["action"] == "CREATE_APPROVED"
    assert payload["actor_id"] == "user-123"
    assert payload["approval_token"] == approval_token


async def test_fr2_1_3_generate_update_draft_shows_before_after_diff(
    service, repository, kg_client
):
    config_id = uuid4()
    current = _make_orm_config(
        config_id=config_id,
        page_title="Old Title",
        meta_description="Old description",
        layout_type_value="STANDARD",
    )
    repository.get_by_id = AsyncMock(return_value=current)

    kg_client.get = AsyncMock(
        side_effect=[
            _make_kg_response({
                "name": "New Title",
                "description": "New description",
                "layout_type": "HERO",
                "visibility_status": "DRAFT",
            }),
            _make_event_types_response(["PRODUCTION"]),
        ]
    )

    result = await service.generate_update_draft(config_id)

    assert result.operation == DiffOperation.UPDATE
    assert "page_title" in result.changes
    assert result.changes["page_title"].before == "Old Title"
    assert result.changes["page_title"].after == "New Title"
    assert "layout_type" in result.changes
    assert result.changes["layout_type"].before == "STANDARD"
    assert result.changes["layout_type"].after == "HERO"
    assert result.prior_state is not None
    assert result.prior_state.page_title == "Old Title"


async def test_fr2_1_4_generate_delete_draft_includes_all_child_records(
    service, repository
):
    config_id = uuid4()

    scroll_section = MagicMock()
    scroll_section.id = uuid4()
    scroll_section.position = 0
    scroll_section.heading = "Section 1"
    scroll_section.content = "Content"
    scroll_section.background_image_url = ""

    from app.backend_implementation.page_config_drafter.models import VisualRepresentationType

    visual_rep = MagicMock()
    visual_rep.id = uuid4()
    visual_rep.type = VisualRepresentationType.IMAGE
    visual_rep.url = "http://example.com/img.jpg"
    visual_rep.alt_text = "Alt"
    visual_rep.position = 0

    event = MagicMock()
    event.id = uuid4()
    event.timestamp = datetime.now(timezone.utc)
    event.event_type = "PRODUCTION"
    event.description = "Produced"

    current = _make_orm_config(
        config_id=config_id,
        scroll_sections=[scroll_section],
        visual_representations=[visual_rep],
        sourcing_timeline_events=[event],
    )
    repository.get_by_id = AsyncMock(return_value=current)

    result = await service.generate_delete_draft(config_id)

    assert result.operation == DiffOperation.DELETE
    assert len(result.draft.scroll_sections) == 1
    assert len(result.draft.visual_representations) == 1
    assert len(result.draft.sourcing_timeline_events) == 1
    assert "page_title" in result.changes
    assert result.changes["page_title"].after is None


async def test_fr2_2_1_create_draft_includes_scroll_sections(service, kg_client):
    kg_client.get = AsyncMock(
        side_effect=[
            _make_kg_response({
                "name": "Product",
                "meta_description": "Desc",
                "scroll_sections": [
                    {"heading": "Section 1", "content": "Content 1", "background_image_url": ""},
                    {"heading": "Section 2", "content": "Content 2", "background_image_url": ""},
                ],
                "visual_representations": [],
                "sourcing_timeline_events": [],
            }),
            _make_event_types_response(["PRODUCTION"]),
        ]
    )

    result = await service.generate_create_draft("prod-123")

    assert len(result.draft.scroll_sections) == 2
    assert result.draft.scroll_sections[0].heading == "Section 1"
    assert result.draft.scroll_sections[1].heading == "Section 2"


async def test_fr2_2_2_create_draft_includes_visual_representations(service, kg_client):
    kg_client.get = AsyncMock(
        side_effect=[
            _make_kg_response({
                "name": "Product",
                "meta_description": "Desc",
                "scroll_sections": [],
                "visual_representations": [
                    {"type": "IMAGE", "url": "http://example.com/img.jpg", "alt_text": "Alt"},
                    {"type": "VIDEO", "url": "http://example.com/vid.mp4", "alt_text": "Video"},
                ],
                "sourcing_timeline_events": [],
            }),
            _make_event_types_response(["PRODUCTION"]),
        ]
    )

    result = await service.generate_create_draft("prod-123")

    assert len(result.draft.visual_representations) == 2
    assert result.draft.visual_representations[0].type == "IMAGE"
    assert result.draft.visual_representations[1].type == "VIDEO"


async def test_fr2_2_3_create_draft_validates_sourcing_timeline_event_types(
    service, kg_client
):
    kg_client.get = AsyncMock(
        side_effect=[
            _make_kg_response({
                "name": "Product",
                "meta_description": "Desc",
                "scroll_sections": [],
                "visual_representations": [],
                "sourcing_timeline_events": [
                    {"event_type": "INVALID_TYPE", "description": "An invalid event"},
                ],
            }),
            _make_event_types_response(["PRODUCTION", "SOURCING"]),
        ]
    )

    result = await service.generate_create_draft("prod-123")

    assert len(result.draft.sourcing_timeline_events) == 1
    assert any("INVALID_TYPE" in w for w in result.draft.validation_warnings)
    assert any("INVALID_TYPE" in w for w in result.validation_warnings)


async def test_fr2_3_1_diff_response_includes_kg_sources_and_reasoning_trace(
    service, kg_client
):
    kg_client.get = AsyncMock(
        side_effect=[
            _make_kg_response({
                "name": "Product",
                "meta_description": "Desc",
                "scroll_sections": [],
                "visual_representations": [],
                "sourcing_timeline_events": [],
            }),
            _make_event_types_response(["PRODUCTION"]),
        ]
    )

    result = await service.generate_create_draft("prod-123")

    assert len(result.kg_sources) > 0
    assert all(
        hasattr(src, "field") and hasattr(src, "source") and hasattr(src, "contribution")
        for src in result.kg_sources
    )
    assert result.reasoning_trace
    assert len(result.reasoning_trace) > 0


async def test_fr2_3_2_rollback_restores_prior_config_version(
    service, repository, session, provenance_client
):
    config_id = uuid4()
    to_version = uuid4()

    current = _make_orm_config(config_id=config_id)
    repository.get_by_id = AsyncMock(return_value=current)
    repository.delete = AsyncMock()

    restored = MagicMock()
    restored.id = uuid4()
    repository.create = AsyncMock(return_value=restored)

    version_response = MagicMock()
    version_response.json.return_value = {
        "config": {
            "product_id": "prod-123",
            "page_title": "Prior Title",
            "meta_description": "Prior desc",
            "layout_type": "STANDARD",
            "visibility_status": "DRAFT",
            "created_by": "user-1",
        },
        "scroll_sections": [],
        "visual_representations": [],
        "sourcing_timeline_events": [],
    }
    version_response.raise_for_status = MagicMock()

    prov_audit_response = MagicMock()
    prov_audit_response.raise_for_status = MagicMock()

    provenance_client.get = AsyncMock(return_value=version_response)
    provenance_client.post = AsyncMock(return_value=prov_audit_response)

    result = await service.rollback_to_version(config_id, to_version, "user-123")

    repository.delete.assert_called_once()
    repository.create.assert_called_once()
    session.commit.assert_called_once()
    provenance_client.post.assert_called_once()
    assert result.status == "RESTORED"


async def test_fr2_4_1_draft_with_missing_required_field_includes_warning(
    service, kg_client
):
    kg_client.get = AsyncMock(
        side_effect=[
            _make_kg_response({
                "scroll_sections": [],
                "visual_representations": [],
                "sourcing_timeline_events": [],
            }),
            _make_event_types_response(["PRODUCTION"]),
        ]
    )

    result = await service.generate_create_draft("prod-123")

    assert any("page_title" in w for w in result.draft.validation_warnings)
    assert any("page_title" in w for w in result.validation_warnings)


async def test_fr2_4_2_approve_draft_without_parent_raises_parent_not_found_error(
    service, repository, session
):
    approval_token = str(uuid4())
    config_id = uuid4()
    draft = PageConfigDraft(
        product_id="prod-123",
        page_title="Test",
        meta_description="Desc",
        layout_type="STANDARD",
        visibility_status="DRAFT",
        workflow_state=WorkflowState.DRAFT_PENDING,
    )
    svc_module._draft_store[approval_token] = {
        "draft": draft,
        "operation": DiffOperation.UPDATE,
        "config_id": str(config_id),
    }

    repository.get_by_id = AsyncMock(side_effect=ConfigNotFoundError("Not found"))

    with pytest.raises(ParentNotFoundError):
        await service.approve_and_persist_draft(approval_token, "user-123")
