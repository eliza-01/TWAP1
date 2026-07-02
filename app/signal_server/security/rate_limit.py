from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from fastapi import Request, WebSocket


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: float = 0.0


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._last_gc_at = 0.0

    def check(
        self,
        key: str,
        max_calls: int,
        window_seconds: float,
        min_interval_seconds: float = 0.0,
    ) -> RateLimitResult:
        now = time.monotonic()
        window = max(float(window_seconds), 1.0)
        self._gc(now, max(window * 2, 120.0))
        limit = max(int(max_calls), 1)
        bucket = self._hits[key]

        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if min_interval_seconds > 0 and bucket and now - bucket[-1] < min_interval_seconds:
            return RateLimitResult(False, min_interval_seconds - (now - bucket[-1]))

        if len(bucket) >= limit:
            return RateLimitResult(False, window - (now - bucket[0]))

        bucket.append(now)
        return RateLimitResult(True)

    def _gc(self, now: float, max_age_seconds: float) -> None:
        if now - self._last_gc_at < 60.0:
            return
        self._last_gc_at = now
        stale = [key for key, bucket in self._hits.items() if not bucket or now - bucket[-1] > max_age_seconds]
        for key in stale:
            self._hits.pop(key, None)


rate_limiter = InMemoryRateLimiter()


def http_identity(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def websocket_identity(websocket: WebSocket) -> str:
    forwarded = (websocket.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    real_ip = (websocket.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    return websocket.client.host if websocket.client else "unknown"


def env_int(name: str, default: int) -> int:
    try:
        return int((os.getenv(name) or "").strip() or default)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float((os.getenv(name) or "").strip() or default)
    except ValueError:
        return default
