from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.exchanges.mexc.constants import DEFAULT_HEADERS


def mexc_signature(auth_token: str, payload: Any) -> tuple[str, str]:
    nonce = str(int(time.time() * 1000))
    seed = hashlib.md5(f"{auth_token}{nonce}".encode()).hexdigest()[7:]
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    sign = hashlib.md5(f"{nonce}{body}{seed}".encode()).hexdigest()
    return nonce, sign


def build_headers(auth_token: str, payload: Any | None = None) -> dict[str, str]:
    headers = dict(DEFAULT_HEADERS)
    if auth_token:
        headers["authorization"] = auth_token
    if payload is not None:
        nonce, sign = mexc_signature(auth_token, payload)
        headers["x-mxc-nonce"] = nonce
        headers["x-mxc-sign"] = sign
    return headers
