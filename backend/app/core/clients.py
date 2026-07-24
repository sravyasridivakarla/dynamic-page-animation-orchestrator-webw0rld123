"""Long-lived HTTP clients for KG Service and Provenance Store with circuit breaker."""

import asyncio
import time

import httpx
import structlog

logger = structlog.get_logger()

_FAILURE_THRESHOLD = 5
_RECOVERY_TIMEOUT = 30.0

_STATE_CLOSED = "closed"
_STATE_OPEN = "open"
_STATE_HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = _FAILURE_THRESHOLD, recovery_timeout: float = _RECOVERY_TIMEOUT):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = _STATE_CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0

    def _transition(self, state: str) -> None:
        if state != self._state:
            logger.info("circuit_breaker_transition", name=self.name, from_state=self._state, to_state=state)
        self._state = state

    def record_success(self) -> None:
        self._failure_count = 0
        self._transition(_STATE_CLOSED)

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._opened_at = time.monotonic()
            self._transition(_STATE_OPEN)

    def allow_request(self) -> bool:
        if self._state == _STATE_CLOSED:
            return True
        if self._state == _STATE_OPEN:
            if time.monotonic() - self._opened_at >= self.recovery_timeout:
                self._transition(_STATE_HALF_OPEN)
                return True
            return False
        # half_open: allow one probe
        return True


class KnowledgeGraphClient:
    def __init__(self, base_url: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        self._cb = CircuitBreaker("kg_service")

    async def get_product_context(self, product_id: str) -> dict:
        if not self._cb.allow_request():
            raise httpx.ConnectError("Circuit breaker open for KG Service")
        try:
            response = await self._client.get(f"/products/{product_id}/context")
            response.raise_for_status()
            self._cb.record_success()
            return response.json()
        except Exception as exc:
            self._cb.record_failure()
            raise

    async def validate_event_types(self, event_types: list) -> dict:
        if not self._cb.allow_request():
            raise httpx.ConnectError("Circuit breaker open for KG Service")
        try:
            response = await self._client.post("/event-types/validate", json={"event_types": event_types})
            response.raise_for_status()
            self._cb.record_success()
            return response.json()
        except Exception as exc:
            self._cb.record_failure()
            raise

    async def aclose(self) -> None:
        await self._client.aclose()


class ProvenanceStoreClient:
    def __init__(self, base_url: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)
        self._cb = CircuitBreaker("provenance_store")

    async def write_event(self, payload: dict) -> dict:
        if not self._cb.allow_request():
            raise httpx.ConnectError("Circuit breaker open for Provenance Store")
        try:
            response = await self._client.post("/events", json=payload)
            response.raise_for_status()
            self._cb.record_success()
            return response.json()
        except Exception as exc:
            self._cb.record_failure()
            raise

    async def get_version_snapshot(self, config_id: str, version: int) -> dict:
        if not self._cb.allow_request():
            raise httpx.ConnectError("Circuit breaker open for Provenance Store")
        try:
            response = await self._client.get(f"/snapshots/{config_id}/versions/{version}")
            response.raise_for_status()
            self._cb.record_success()
            return response.json()
        except Exception as exc:
            self._cb.record_failure()
            raise

    async def aclose(self) -> None:
        await self._client.aclose()
