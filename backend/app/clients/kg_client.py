"""Knowledge Graph Service async HTTP client."""

from typing import Any, Dict, List

import httpx


class KGServiceUnavailableError(Exception):
    pass


class KnowledgeGraphClient:
    def __init__(self, base_url: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def get_product_context(self, product_id: str) -> Dict[str, Any]:
        try:
            resp = await self._client.get(f"/products/{product_id}/context")
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            raise KGServiceUnavailableError(str(exc)) from exc

    async def validate_event_types(self, event_types: List[str]) -> Dict[str, bool]:
        try:
            resp = await self._client.post(
                "/event-types/validate", json={"event_types": event_types}
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            raise KGServiceUnavailableError(str(exc)) from exc

    async def aclose(self) -> None:
        await self._client.aclose()
