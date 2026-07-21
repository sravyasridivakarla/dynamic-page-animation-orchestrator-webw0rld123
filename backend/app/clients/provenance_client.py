"""Provenance and Trace Store async HTTP client."""

from typing import Any, Dict

import httpx


class ProvenanceStoreUnavailableError(Exception):
    pass


class ProvenanceStoreClient:
    def __init__(self, base_url: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def record_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resp = await self._client.post("/actions", json=payload)
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            raise ProvenanceStoreUnavailableError(str(exc)) from exc

    async def check_health(self) -> bool:
        try:
            resp = await self._client.get("/health")
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def aclose(self) -> None:
        await self._client.aclose()
