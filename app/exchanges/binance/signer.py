from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

from app.exchanges.binance.constants import DEFAULT_HEADERS, RECV_WINDOW


def build_headers(api_key: str) -> dict[str, str]:
    headers = dict(DEFAULT_HEADERS)
    if api_key:
        headers["X-MBX-APIKEY"] = api_key
    return headers


def signed_params(
    secret_key: str,
    params: dict[str, Any] | None = None,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = dict(params or {})
    payload.setdefault("recvWindow", RECV_WINDOW)
    payload["timestamp"] = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    query = urlencode(payload, doseq=True)
    payload["signature"] = hmac.new(secret_key.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    return payload
