from __future__ import annotations

import json
from typing import Any

import httpx

from app.exchanges.core.errors import ExchangeRequestError
from app.exchanges.mexc.constants import API_BASE_URL
from app.exchanges.mexc.signer import build_headers


class MexcFuturesClient:
    def __init__(self, auth_token: str, base_url: str = API_BASE_URL, timeout: float = 20.0) -> None:
        self.auth_token = auth_token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, payload: Any) -> dict[str, Any]:
        return await self._request("POST", endpoint, json_body=payload)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> dict[str, Any]:
        headers = build_headers(self.auth_token, json_body if method == "POST" else None)
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, params=params, json=json_body, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:1000] if exc.response is not None else ""
            raise ExchangeRequestError(f"MEXC HTTP {exc.response.status_code}: {body}") from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise ExchangeRequestError(f"MEXC request failed: {exc}") from exc

        if isinstance(data, dict) and data.get("success") is False:
            raise ExchangeRequestError(str(data.get("message") or data.get("code") or data))
        if not isinstance(data, dict):
            raise ExchangeRequestError(f"Unexpected MEXC response: {data!r}")
        return data
