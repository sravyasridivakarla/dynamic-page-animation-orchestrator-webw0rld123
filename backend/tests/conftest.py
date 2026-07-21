"""Pytest fixtures."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_kg_client():
    client = AsyncMock()
    client.get_product_context = AsyncMock(
        return_value={"product_id": "prod-1", "catalog": {"name": "Test Product"}}
    )
    client.validate_event_types = AsyncMock(
        return_value={"launch": True, "sourcing": True}
    )
    return client


@pytest.fixture
def mock_provenance_client():
    client = AsyncMock()
    client.record_action = AsyncMock(return_value={"id": str(uuid4()), "status": "recorded"})
    client.check_health = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    return session
